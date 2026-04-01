"""
Project Aura - Higher-Order Bug Queue for Self-Play SWE-RL

Manages a priority queue of higher-order bugs derived from failed
solve attempts, enabling curriculum learning through progressively
harder training examples.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 5

Key Features:
- Failed attempts → new training examples
- Priority queue by difficulty level
- Deduplication of similar bugs
- Staleness detection and pruning
- Balanced sampling across difficulty levels

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issue: #165
"""

from __future__ import annotations

import hashlib
import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.ssr.failure_analyzer import FailureAnalysis, FailureSummary

logger = logging.getLogger(__name__)


class QueuePriority(Enum):
    """Priority levels for higher-order bugs."""

    CRITICAL = 1  # Highest priority - severe failure patterns
    HIGH = 2  # High difficulty delta
    MEDIUM = 3  # Standard higher-order bugs
    LOW = 4  # Low priority - marginal candidates


class BugStatus(Enum):
    """Status of a bug in the queue."""

    PENDING = "pending"  # Waiting to be processed
    ACTIVE = "active"  # Currently being used for training
    COMPLETED = "completed"  # Successfully trained on
    STALE = "stale"  # Marked as stale, pending pruning
    DEDUPLICATED = "deduplicated"  # Merged with another bug


@dataclass
class HigherOrderBug:
    """A higher-order bug derived from failed solve attempts."""

    bug_id: str
    original_artifact_id: str
    repository_id: str
    difficulty: int  # 1-10
    priority: QueuePriority
    status: BugStatus = BugStatus.PENDING

    # Failure analysis data
    failure_modes: list[str] = field(default_factory=list)
    learning_signals: list[str] = field(default_factory=list)
    error_patterns: list[str] = field(default_factory=list)

    # Content signature for deduplication
    content_hash: str = ""

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    training_count: int = 0  # Times used in training

    # Parent-child relationships
    parent_bug_id: str | None = None  # If derived from another higher-order bug
    child_bug_ids: list[str] = field(default_factory=list)

    def __lt__(self, other: HigherOrderBug) -> bool:
        """Compare for heap ordering (lower priority value = higher priority)."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # Secondary sort by difficulty (higher difficulty first)
        return self.difficulty > other.difficulty

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "bug_id": self.bug_id,
            "original_artifact_id": self.original_artifact_id,
            "repository_id": self.repository_id,
            "difficulty": self.difficulty,
            "priority": self.priority.value,
            "status": self.status.value,
            "failure_modes": self.failure_modes,
            "learning_signals": self.learning_signals,
            "error_patterns": self.error_patterns,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "training_count": self.training_count,
            "parent_bug_id": self.parent_bug_id,
            "child_bug_ids": self.child_bug_ids,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HigherOrderBug:
        """Deserialize from dictionary."""
        return cls(
            bug_id=data["bug_id"],
            original_artifact_id=data["original_artifact_id"],
            repository_id=data["repository_id"],
            difficulty=data["difficulty"],
            priority=QueuePriority(data["priority"]),
            status=BugStatus(data["status"]),
            failure_modes=data.get("failure_modes", []),
            learning_signals=data.get("learning_signals", []),
            error_patterns=data.get("error_patterns", []),
            content_hash=data.get("content_hash", ""),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now(timezone.utc)
            ),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"])
                if "last_accessed" in data
                else datetime.now(timezone.utc)
            ),
            access_count=data.get("access_count", 0),
            training_count=data.get("training_count", 0),
            parent_bug_id=data.get("parent_bug_id"),
            child_bug_ids=data.get("child_bug_ids", []),
        )


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""

    is_duplicate: bool
    duplicate_of: str | None = None
    similarity_score: float = 0.0
    merged: bool = False


class HigherOrderQueue:
    """
    Priority queue for higher-order bugs derived from failed solve attempts.

    This queue manages bugs that were too difficult for the solver,
    enabling curriculum learning by presenting progressively harder
    challenges to the training process.

    Usage:
        queue = HigherOrderQueue()

        # Add a higher-order bug from failure analysis
        bug = queue.add_from_failure(failure_summary, analyses)

        # Get next bug for training
        next_bug = queue.get_next()

        # Mark as completed after training
        queue.mark_completed(bug.bug_id)

        # Get balanced sample for training batch
        bugs = queue.get_balanced_sample(batch_size=32)
    """

    def __init__(
        self,
        max_queue_size: int = 10000,
        staleness_days: int = 30,
        similarity_threshold: float = 0.8,
        max_training_uses: int = 5,
    ):
        """
        Initialize the higher-order queue.

        Args:
            max_queue_size: Maximum bugs in queue
            staleness_days: Days before a bug is considered stale
            similarity_threshold: Threshold for deduplication (0-1)
            max_training_uses: Max times a bug can be used for training
        """
        self.max_queue_size = max_queue_size
        self.staleness_days = staleness_days
        self.similarity_threshold = similarity_threshold
        self.max_training_uses = max_training_uses

        # Priority heap (min-heap based on priority value)
        self._heap: list[HigherOrderBug] = []

        # Fast lookup by ID
        self._bugs_by_id: dict[str, HigherOrderBug] = {}

        # Content hash index for deduplication
        self._hash_index: dict[str, str] = {}  # content_hash -> bug_id

        # Error pattern inverted index for O(1) duplicate pattern lookup
        self._pattern_to_bugs: dict[str, set[str]] = {}  # pattern -> set of bug_ids

        # Difficulty distribution tracking
        self._difficulty_counts: dict[int, int] = dict.fromkeys(range(1, 11), 0)

        # Statistics
        self._total_added = 0
        self._total_deduplicated = 0
        self._total_pruned = 0

        logger.info(
            f"HigherOrderQueue initialized: max_size={max_queue_size}, "
            f"staleness={staleness_days}d, similarity_threshold={similarity_threshold}"
        )

    def add_from_failure(
        self,
        summary: FailureSummary,
        analyses: list[FailureAnalysis],
        repository_id: str,
        parent_bug_id: str | None = None,
    ) -> HigherOrderBug | None:
        """
        Add a higher-order bug from failure analysis.

        Args:
            summary: Failure summary for the artifact
            analyses: Individual failure analyses
            repository_id: Repository the bug came from
            parent_bug_id: Parent bug ID if this is derived from another higher-order bug

        Returns:
            The created HigherOrderBug, or None if deduplicated/rejected
        """
        if not summary.is_higher_order_candidate:
            logger.debug(f"Artifact {summary.artifact_id} not a higher-order candidate")
            return None

        # Generate content hash for deduplication
        content_hash = self._generate_content_hash(summary, analyses)

        # Check for duplicates
        dedup_result = self._check_duplicate(content_hash, analyses)
        if dedup_result.is_duplicate:
            logger.debug(
                f"Bug deduplicated with {dedup_result.duplicate_of} "
                f"(similarity: {dedup_result.similarity_score:.2f})"
            )
            self._total_deduplicated += 1
            return None

        # Determine priority
        priority = self._calculate_priority(summary, analyses)

        # Create the bug
        bug = HigherOrderBug(
            bug_id=f"hob-{hashlib.sha256(content_hash.encode()).hexdigest()[:12]}",
            original_artifact_id=summary.artifact_id,
            repository_id=repository_id,
            difficulty=summary.recommended_difficulty,
            priority=priority,
            failure_modes=[m.value for m in summary.failure_modes.keys()],
            learning_signals=[s.value for s in summary.learning_signals.keys()],
            error_patterns=self._aggregate_error_patterns(analyses),
            content_hash=content_hash,
            parent_bug_id=parent_bug_id,
        )

        # Add to queue
        self._add_bug(bug)

        # Update parent if exists
        if parent_bug_id and parent_bug_id in self._bugs_by_id:
            self._bugs_by_id[parent_bug_id].child_bug_ids.append(bug.bug_id)

        logger.info(
            f"Added higher-order bug {bug.bug_id}: "
            f"difficulty={bug.difficulty}, priority={priority.name}"
        )

        return bug

    def get_next(self) -> HigherOrderBug | None:
        """
        Get the next highest priority bug for training.

        Returns:
            The next bug, or None if queue is empty
        """
        while self._heap:
            bug = heapq.heappop(self._heap)

            # Skip if already processed
            if bug.bug_id not in self._bugs_by_id:
                continue

            # Skip if stale
            if bug.status == BugStatus.STALE:
                continue

            # Skip if over-trained
            if bug.training_count >= self.max_training_uses:
                bug.status = BugStatus.COMPLETED
                continue

            # Update access metadata
            bug.last_accessed = datetime.now(timezone.utc)
            bug.access_count += 1
            bug.status = BugStatus.ACTIVE

            # Re-add to heap for next access
            heapq.heappush(self._heap, bug)

            return bug

        return None

    def get_balanced_sample(
        self,
        batch_size: int = 32,
        difficulty_weights: dict[int, float] | None = None,
    ) -> list[HigherOrderBug]:
        """
        Get a balanced sample of bugs across difficulty levels.

        Args:
            batch_size: Number of bugs to sample
            difficulty_weights: Optional weights for each difficulty (1-10)

        Returns:
            List of sampled bugs
        """
        if not difficulty_weights:
            # Default: favor medium-high difficulty
            difficulty_weights = {
                1: 0.05,
                2: 0.05,
                3: 0.08,
                4: 0.10,
                5: 0.12,
                6: 0.15,
                7: 0.15,
                8: 0.12,
                9: 0.10,
                10: 0.08,
            }

        # Group bugs by difficulty
        by_difficulty: dict[int, list[HigherOrderBug]] = {i: [] for i in range(1, 11)}
        for bug in self._bugs_by_id.values():
            if bug.status in (BugStatus.PENDING, BugStatus.ACTIVE):
                by_difficulty[bug.difficulty].append(bug)

        # Sample according to weights
        import random

        sample: list[HigherOrderBug] = []
        for difficulty, weight in difficulty_weights.items():
            target_count = int(batch_size * weight)
            available = by_difficulty.get(difficulty, [])
            if available:
                selected = random.sample(available, min(target_count, len(available)))
                sample.extend(selected)

        # Update access metadata
        for bug in sample:
            bug.last_accessed = datetime.now(timezone.utc)
            bug.access_count += 1

        random.shuffle(sample)
        return sample[:batch_size]

    def mark_completed(self, bug_id: str, success: bool = True) -> None:
        """
        Mark a bug as completed after training.

        Args:
            bug_id: The bug ID
            success: Whether training was successful
        """
        if bug_id not in self._bugs_by_id:
            return

        bug = self._bugs_by_id[bug_id]
        bug.training_count += 1

        if bug.training_count >= self.max_training_uses:
            bug.status = BugStatus.COMPLETED
            self._difficulty_counts[bug.difficulty] -= 1
        else:
            bug.status = BugStatus.PENDING

        logger.debug(
            f"Bug {bug_id} training #{bug.training_count} "
            f"{'completed' if success else 'failed'}"
        )

    def prune_stale(self) -> int:
        """
        Remove stale bugs from the queue.

        Returns:
            Number of bugs pruned
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.staleness_days)
        stale_ids = []

        for bug_id, bug in self._bugs_by_id.items():
            if bug.last_accessed < cutoff and bug.status != BugStatus.COMPLETED:
                bug.status = BugStatus.STALE
                stale_ids.append(bug_id)

        for bug_id in stale_ids:
            self._remove_bug(bug_id)

        self._total_pruned += len(stale_ids)
        logger.info(f"Pruned {len(stale_ids)} stale bugs")

        return len(stale_ids)

    def _add_bug(self, bug: HigherOrderBug) -> None:
        """Add a bug to the queue."""
        # Check queue capacity
        if len(self._bugs_by_id) >= self.max_queue_size:
            self._evict_lowest_priority()

        self._bugs_by_id[bug.bug_id] = bug
        self._hash_index[bug.content_hash] = bug.bug_id
        self._difficulty_counts[bug.difficulty] += 1
        heapq.heappush(self._heap, bug)
        self._total_added += 1

        # Update error pattern inverted index
        for pattern in bug.error_patterns:
            p_lower = pattern.lower()
            if p_lower not in self._pattern_to_bugs:
                self._pattern_to_bugs[p_lower] = set()
            self._pattern_to_bugs[p_lower].add(bug.bug_id)

    def _remove_bug(self, bug_id: str) -> None:
        """Remove a bug from the queue."""
        if bug_id not in self._bugs_by_id:
            return

        bug = self._bugs_by_id[bug_id]
        del self._bugs_by_id[bug_id]

        if bug.content_hash in self._hash_index:
            del self._hash_index[bug.content_hash]

        # Clean up error pattern inverted index
        for pattern in bug.error_patterns:
            p_lower = pattern.lower()
            if p_lower in self._pattern_to_bugs:
                self._pattern_to_bugs[p_lower].discard(bug_id)
                if not self._pattern_to_bugs[p_lower]:
                    del self._pattern_to_bugs[p_lower]

        self._difficulty_counts[bug.difficulty] = max(
            0, self._difficulty_counts[bug.difficulty] - 1
        )

    def _evict_lowest_priority(self) -> None:
        """Evict the lowest priority bug to make room."""
        if not self._bugs_by_id:
            return

        # Find lowest priority (highest priority value, lowest difficulty)
        lowest = None
        for bug in self._bugs_by_id.values():
            if bug.status in (BugStatus.PENDING, BugStatus.STALE):
                if lowest is None or (
                    bug.priority.value > lowest.priority.value
                    or (
                        bug.priority.value == lowest.priority.value
                        and bug.difficulty < lowest.difficulty
                    )
                ):
                    lowest = bug

        if lowest:
            self._remove_bug(lowest.bug_id)
            logger.debug(f"Evicted bug {lowest.bug_id} to make room")

    def _generate_content_hash(
        self,
        summary: FailureSummary,
        analyses: list[FailureAnalysis],
    ) -> str:
        """Generate a content hash for deduplication."""
        # Combine key features
        features = [
            summary.artifact_id,
            str(sorted(m.value for m in summary.failure_modes.keys())),
            str(sorted(s.value for s in summary.learning_signals.keys())),
        ]

        # Add error patterns from analyses
        all_patterns = []
        for analysis in analyses:
            all_patterns.extend(analysis.error_patterns)

        # Normalize and sort patterns
        normalized = sorted({p.lower().strip() for p in all_patterns})
        features.append(str(normalized[:10]))

        return hashlib.sha256("|".join(features).encode()).hexdigest()

    def _check_duplicate(
        self,
        content_hash: str,
        analyses: list[FailureAnalysis],
    ) -> DeduplicationResult:
        """Check if this bug is a duplicate of an existing one."""
        # Exact hash match
        if content_hash in self._hash_index:
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_of=self._hash_index[content_hash],
                similarity_score=1.0,
            )

        # Fuzzy matching based on error patterns using inverted index
        new_patterns: set[str] = set()
        for analysis in analyses:
            new_patterns.update({p.lower() for p in analysis.error_patterns})

        if not new_patterns:
            return DeduplicationResult(is_duplicate=False)

        # Use inverted index to find candidate bugs that share at least one pattern
        candidate_bug_ids: set[str] = set()
        for pattern in new_patterns:
            if pattern in self._pattern_to_bugs:
                candidate_bug_ids.update(self._pattern_to_bugs[pattern])

        for bug_id in candidate_bug_ids:
            bug = self._bugs_by_id.get(bug_id)
            if not bug:
                continue

            existing_patterns = {p.lower() for p in bug.error_patterns}
            if not existing_patterns:
                continue

            # Jaccard similarity
            intersection = len(new_patterns & existing_patterns)
            union = len(new_patterns | existing_patterns)
            similarity = intersection / union if union > 0 else 0

            if similarity >= self.similarity_threshold:
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_of=bug_id,
                    similarity_score=similarity,
                )

        return DeduplicationResult(is_duplicate=False)

    def _calculate_priority(
        self,
        summary: FailureSummary,
        analyses: list[FailureAnalysis],
    ) -> QueuePriority:
        """Calculate queue priority for a bug."""
        # Critical: timeout + high difficulty
        if summary.recommended_difficulty >= 8 and any(
            "timeout" in a.failure_mode.value for a in analyses
        ):
            return QueuePriority.CRITICAL

        # High: consistent semantic errors
        semantic_count = sum(
            1
            for a in analyses
            if a.failure_mode.value in ("semantic_error", "wrong_fix")
        )
        if semantic_count >= len(analyses) * 0.7:
            return QueuePriority.HIGH

        # High: high difficulty
        if summary.recommended_difficulty >= 7:
            return QueuePriority.HIGH

        # Medium: standard candidates
        if summary.avg_difficulty_delta >= 2:
            return QueuePriority.MEDIUM

        return QueuePriority.LOW

    def _aggregate_error_patterns(
        self,
        analyses: list[FailureAnalysis],
    ) -> list[str]:
        """Aggregate and deduplicate error patterns from analyses."""
        pattern_counts: dict[str, int] = {}

        for analysis in analyses:
            for pattern in analysis.error_patterns:
                normalized = pattern.lower().strip()
                pattern_counts[normalized] = pattern_counts.get(normalized, 0) + 1

        # Sort by frequency and return top patterns
        sorted_patterns = sorted(
            pattern_counts.items(), key=lambda x: x[1], reverse=True
        )

        return [p for p, _ in sorted_patterns[:15]]

    def get_difficulty_distribution(self) -> dict[int, int]:
        """Get the distribution of bugs by difficulty."""
        return dict(self._difficulty_counts)

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return len(self._bugs_by_id)

    def get_metrics(self) -> dict[str, Any]:
        """Get queue metrics."""
        status_counts = {}
        for bug in self._bugs_by_id.values():
            status = bug.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        priority_counts = {}
        for bug in self._bugs_by_id.values():
            priority = bug.priority.name
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        return {
            "queue_size": len(self._bugs_by_id),
            "heap_size": len(self._heap),
            "difficulty_distribution": self.get_difficulty_distribution(),
            "status_distribution": status_counts,
            "priority_distribution": priority_counts,
            "total_added": self._total_added,
            "total_deduplicated": self._total_deduplicated,
            "total_pruned": self._total_pruned,
            "deduplication_rate": (
                self._total_deduplicated / self._total_added
                if self._total_added > 0
                else 0
            ),
        }

    def clear(self) -> None:
        """Clear the queue."""
        self._heap.clear()
        self._bugs_by_id.clear()
        self._hash_index.clear()
        self._difficulty_counts = dict.fromkeys(range(1, 11), 0)
        logger.info("Higher-order queue cleared")
