"""
Tests for SSR Higher-Order Bug Queue.

Tests the priority queue for failed bugs with deduplication,
batch sampling, and staleness pruning.
"""

from datetime import datetime, timezone

import pytest

from src.services.ssr.higher_order_queue import (
    BugStatus,
    DeduplicationResult,
    HigherOrderBug,
    HigherOrderQueue,
    QueuePriority,
)

# Note: pytest.mark.forked disabled for accurate coverage measurement
# The module has well-isolated tests that don't require process isolation
# pytestmark = pytest.mark.forked


class TestQueuePriorityEnum:
    """Tests for QueuePriority enum."""

    def test_all_priorities_defined(self):
        """Verify all expected priorities exist."""
        # QueuePriority uses integer values for heap ordering
        expected = {1, 2, 3, 4}
        actual = {p.value for p in QueuePriority}
        assert expected == actual

    def test_priority_names(self):
        """Test priority name values."""
        assert QueuePriority.CRITICAL.value == 1
        assert QueuePriority.HIGH.value == 2
        assert QueuePriority.MEDIUM.value == 3
        assert QueuePriority.LOW.value == 4


class TestBugStatusEnum:
    """Tests for BugStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all expected statuses exist."""
        expected = {"pending", "active", "completed", "stale", "deduplicated"}
        actual = {s.value for s in BugStatus}
        assert expected == actual


class TestHigherOrderBug:
    """Tests for HigherOrderBug dataclass."""

    def test_bug_creation(self):
        """Test creating a higher-order bug."""
        now = datetime.now(timezone.utc)
        bug = HigherOrderBug(
            bug_id="bug-123",
            original_artifact_id="art-456",
            repository_id="repo-789",
            difficulty=7,
            priority=QueuePriority.HIGH,
            status=BugStatus.PENDING,
            failure_modes=["timeout", "wrong_fix"],
            learning_signals=["edge_case_missed"],
            created_at=now,
        )
        assert bug.bug_id == "bug-123"
        assert bug.priority == QueuePriority.HIGH
        assert bug.status == BugStatus.PENDING
        assert bug.difficulty == 7

    def test_bug_serialization(self):
        """Test serialization and deserialization."""
        now = datetime.now(timezone.utc)
        bug = HigherOrderBug(
            bug_id="bug-123",
            original_artifact_id="art-456",
            repository_id="repo-789",
            difficulty=5,
            priority=QueuePriority.MEDIUM,
            status=BugStatus.PENDING,
            failure_modes=["timeout"],
            learning_signals=["context_insufficient"],
            created_at=now,
        )
        data = bug.to_dict()
        restored = HigherOrderBug.from_dict(data)
        assert restored.bug_id == bug.bug_id
        assert restored.priority == bug.priority
        assert restored.difficulty == bug.difficulty

    def test_bug_comparison(self):
        """Test heap ordering comparison."""
        critical_bug = HigherOrderBug(
            bug_id="bug-1",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.CRITICAL,
        )
        low_bug = HigherOrderBug(
            bug_id="bug-2",
            original_artifact_id="art-2",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.LOW,
        )
        # Critical (value=1) < Low (value=4) for heap ordering
        assert critical_bug < low_bug


class TestHigherOrderQueue:
    """Tests for HigherOrderQueue service."""

    @pytest.fixture
    def queue(self):
        """Create a HigherOrderQueue instance."""
        return HigherOrderQueue()

    def test_queue_initialization(self, queue):
        """Test queue initialization."""
        assert queue.get_queue_size() == 0
        assert queue.max_queue_size == 10000

    def test_custom_initialization(self):
        """Test queue with custom parameters."""
        queue = HigherOrderQueue(
            max_queue_size=500,
            staleness_days=14,
            similarity_threshold=0.9,
        )
        assert queue.max_queue_size == 500
        assert queue.staleness_days == 14
        assert queue.similarity_threshold == 0.9

    def test_get_next_empty_queue(self, queue):
        """Test getting next from empty queue."""
        bug = queue.get_next()
        assert bug is None

    def test_get_queue_metrics(self, queue):
        """Test getting queue metrics."""
        metrics = queue.get_metrics()
        assert "queue_size" in metrics
        assert "total_added" in metrics
        assert "total_deduplicated" in metrics
        assert "difficulty_distribution" in metrics

    def test_get_difficulty_distribution(self, queue):
        """Test difficulty distribution tracking."""
        distribution = queue.get_difficulty_distribution()
        # Should have all difficulty levels 1-10
        assert len(distribution) == 10
        for i in range(1, 11):
            assert i in distribution

    def test_clear_queue(self, queue):
        """Test clearing the queue."""
        queue.clear()
        assert queue.get_queue_size() == 0


class TestDeduplication:
    """Tests for deduplication functionality."""

    def test_deduplication_result_creation(self):
        """Test DeduplicationResult dataclass."""
        result = DeduplicationResult(
            is_duplicate=True,
            duplicate_of="bug-1",
            similarity_score=0.95,
            merged=False,
        )
        assert result.is_duplicate is True
        assert result.similarity_score == 0.95
        assert result.duplicate_of == "bug-1"

    def test_deduplication_result_defaults(self):
        """Test DeduplicationResult default values."""
        result = DeduplicationResult(is_duplicate=False)
        assert result.duplicate_of is None
        assert result.similarity_score == 0.0
        assert result.merged is False


# =============================================================================
# Mock Fixtures for Failure Analysis
# =============================================================================


@pytest.fixture
def mock_failure_mode():
    """Import FailureMode enum."""
    from src.services.ssr.failure_analyzer import FailureMode

    return FailureMode


@pytest.fixture
def mock_learning_signal():
    """Import LearningSignalType enum."""
    from src.services.ssr.failure_analyzer import LearningSignalType

    return LearningSignalType


@pytest.fixture
def mock_failure_analysis(mock_failure_mode, mock_learning_signal):
    """Create a mock FailureAnalysis."""
    from src.services.ssr.failure_analyzer import FailureAnalysis

    return FailureAnalysis(
        attempt_id="attempt-123",
        artifact_id="art-456",
        failure_mode=mock_failure_mode.TIMEOUT,
        learning_signals=[mock_learning_signal.COMPLEXITY_UNDERESTIMATE],
        difficulty_delta=2,
        confidence=0.85,
        error_patterns=["connection reset", "timeout after 30s"],
    )


@pytest.fixture
def mock_failure_summary(mock_failure_mode, mock_learning_signal):
    """Create a mock FailureSummary that is a higher-order candidate."""
    from src.services.ssr.failure_analyzer import FailureSummary

    return FailureSummary(
        artifact_id="art-456",
        total_attempts=5,
        failure_modes={mock_failure_mode.TIMEOUT: 3, mock_failure_mode.WRONG_FIX: 2},
        learning_signals={
            mock_learning_signal.COMPLEXITY_UNDERESTIMATE: 3,
            mock_learning_signal.EDGE_CASE_MISSED: 2,
        },
        avg_difficulty_delta=3.5,
        is_higher_order_candidate=True,
        recommended_difficulty=8,
    )


@pytest.fixture
def mock_failure_summary_not_candidate(mock_failure_mode, mock_learning_signal):
    """Create a mock FailureSummary that is NOT a higher-order candidate."""
    from src.services.ssr.failure_analyzer import FailureSummary

    return FailureSummary(
        artifact_id="art-789",
        total_attempts=2,
        failure_modes={mock_failure_mode.SYNTAX_ERROR: 2},
        learning_signals={},
        avg_difficulty_delta=0.5,
        is_higher_order_candidate=False,
        recommended_difficulty=3,
    )


# =============================================================================
# Add From Failure Tests
# =============================================================================


class TestAddFromFailure:
    """Tests for add_from_failure method."""

    @pytest.fixture
    def queue(self):
        """Create a queue instance."""
        return HigherOrderQueue()

    def test_add_from_failure_creates_bug(
        self,
        queue,
        mock_failure_summary,
        mock_failure_analysis,
    ):
        """Test that add_from_failure creates a higher-order bug."""
        bug = queue.add_from_failure(
            summary=mock_failure_summary,
            analyses=[mock_failure_analysis],
            repository_id="repo-1",
        )

        assert bug is not None
        assert bug.bug_id.startswith("hob-")
        assert bug.repository_id == "repo-1"
        assert bug.difficulty == 8
        assert queue.get_queue_size() == 1

    def test_add_from_failure_not_candidate_returns_none(
        self,
        queue,
        mock_failure_summary_not_candidate,
        mock_failure_analysis,
    ):
        """Test that non-candidates are rejected."""
        bug = queue.add_from_failure(
            summary=mock_failure_summary_not_candidate,
            analyses=[mock_failure_analysis],
            repository_id="repo-1",
        )

        assert bug is None
        assert queue.get_queue_size() == 0

    def test_add_from_failure_with_parent(
        self,
        queue,
        mock_failure_summary,
        mock_failure_analysis,
    ):
        """Test adding a higher-order bug with parent relationship."""
        # Add first bug
        parent = queue.add_from_failure(
            summary=mock_failure_summary,
            analyses=[mock_failure_analysis],
            repository_id="repo-1",
        )

        # Create a different failure summary
        from src.services.ssr.failure_analyzer import (
            FailureMode,
            FailureSummary,
            LearningSignalType,
        )

        child_summary = FailureSummary(
            artifact_id="art-child",
            total_attempts=3,
            failure_modes={FailureMode.SEMANTIC_ERROR: 3},
            learning_signals={LearningSignalType.LOGIC_ERROR: 2},
            avg_difficulty_delta=4.0,
            is_higher_order_candidate=True,
            recommended_difficulty=9,
        )

        from src.services.ssr.failure_analyzer import FailureAnalysis

        child_analysis = FailureAnalysis(
            attempt_id="attempt-child",
            artifact_id="art-child",
            failure_mode=FailureMode.SEMANTIC_ERROR,
            error_patterns=["different pattern"],
        )

        child = queue.add_from_failure(
            summary=child_summary,
            analyses=[child_analysis],
            repository_id="repo-1",
            parent_bug_id=parent.bug_id,
        )

        assert child is not None
        assert child.parent_bug_id == parent.bug_id
        # Parent should have child in child_bug_ids
        assert child.bug_id in queue._bugs_by_id[parent.bug_id].child_bug_ids

    def test_add_from_failure_deduplication(
        self,
        queue,
        mock_failure_summary,
        mock_failure_analysis,
    ):
        """Test that duplicate bugs are detected and rejected."""
        # Add first bug
        bug1 = queue.add_from_failure(
            summary=mock_failure_summary,
            analyses=[mock_failure_analysis],
            repository_id="repo-1",
        )

        # Try to add the same bug again (same content hash)
        bug2 = queue.add_from_failure(
            summary=mock_failure_summary,
            analyses=[mock_failure_analysis],
            repository_id="repo-1",
        )

        assert bug1 is not None
        assert bug2 is None  # Deduplicated
        assert queue.get_queue_size() == 1
        assert queue._total_deduplicated == 1


# =============================================================================
# Get Next Tests
# =============================================================================


class TestGetNext:
    """Tests for get_next method."""

    @pytest.fixture
    def queue_with_bugs(self):
        """Create a queue with some bugs."""
        queue = HigherOrderQueue()

        for i, priority in enumerate(
            [
                QueuePriority.LOW,
                QueuePriority.CRITICAL,
                QueuePriority.MEDIUM,
            ]
        ):
            bug = HigherOrderBug(
                bug_id=f"bug-{i}",
                original_artifact_id=f"art-{i}",
                repository_id="repo-1",
                difficulty=5,
                priority=priority,
                content_hash=f"hash-{i}",
            )
            queue._add_bug(bug)

        return queue

    def test_get_next_returns_highest_priority(self, queue_with_bugs):
        """Test that get_next returns highest priority bug first."""
        bug = queue_with_bugs.get_next()

        assert bug is not None
        assert bug.priority == QueuePriority.CRITICAL  # Highest priority

    def test_get_next_updates_metadata(self, queue_with_bugs):
        """Test that get_next updates access metadata."""
        bug = queue_with_bugs.get_next()

        assert bug.access_count == 1
        assert bug.status == BugStatus.ACTIVE

    def test_get_next_skips_stale(self, queue_with_bugs):
        """Test that get_next skips stale bugs."""
        # Mark critical bug as stale
        queue_with_bugs._bugs_by_id["bug-1"].status = BugStatus.STALE

        bug = queue_with_bugs.get_next()

        # Should get next priority (MEDIUM or LOW)
        assert bug is not None
        assert bug.priority != QueuePriority.CRITICAL

    def test_get_next_skips_over_trained(self, queue_with_bugs):
        """Test that get_next skips over-trained bugs."""
        queue_with_bugs.max_training_uses = 2

        # Over-train the critical bug
        queue_with_bugs._bugs_by_id["bug-1"].training_count = 5

        bug = queue_with_bugs.get_next()

        # Should skip the over-trained critical bug
        assert bug.bug_id != "bug-1"


# =============================================================================
# Get Balanced Sample Tests
# =============================================================================


class TestGetBalancedSample:
    """Tests for get_balanced_sample method."""

    @pytest.fixture
    def queue_with_varied_difficulty(self):
        """Create a queue with bugs at various difficulty levels."""
        queue = HigherOrderQueue()

        # Add 10 bugs at each difficulty level
        for difficulty in range(1, 11):
            for i in range(10):
                bug = HigherOrderBug(
                    bug_id=f"bug-{difficulty}-{i}",
                    original_artifact_id=f"art-{difficulty}-{i}",
                    repository_id="repo-1",
                    difficulty=difficulty,
                    priority=QueuePriority.MEDIUM,
                    content_hash=f"hash-{difficulty}-{i}",
                )
                queue._add_bug(bug)

        return queue

    def test_get_balanced_sample_returns_bugs(self, queue_with_varied_difficulty):
        """Test that balanced sample returns bugs."""
        sample = queue_with_varied_difficulty.get_balanced_sample(batch_size=20)

        assert len(sample) <= 20
        assert len(sample) > 0

    def test_get_balanced_sample_updates_metadata(self, queue_with_varied_difficulty):
        """Test that sampling updates access metadata."""
        sample = queue_with_varied_difficulty.get_balanced_sample(batch_size=10)

        for bug in sample:
            assert bug.access_count >= 1

    def test_get_balanced_sample_custom_weights(self, queue_with_varied_difficulty):
        """Test balanced sample with custom difficulty weights."""
        # Weight heavily toward difficulty 10
        weights = {i: 0.01 for i in range(1, 10)}
        weights[10] = 0.91

        sample = queue_with_varied_difficulty.get_balanced_sample(
            batch_size=20, difficulty_weights=weights
        )

        # Most samples should be difficulty 10
        diff_10_count = sum(1 for b in sample if b.difficulty == 10)
        assert diff_10_count > len(sample) // 2


# =============================================================================
# Mark Completed Tests
# =============================================================================


class TestMarkCompleted:
    """Tests for mark_completed method."""

    @pytest.fixture
    def queue_with_bug(self):
        """Create a queue with one bug."""
        queue = HigherOrderQueue(max_training_uses=3)
        bug = HigherOrderBug(
            bug_id="bug-1",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.MEDIUM,
            content_hash="hash-1",
        )
        queue._add_bug(bug)
        return queue

    def test_mark_completed_increments_training_count(self, queue_with_bug):
        """Test that mark_completed increments training count."""
        queue_with_bug.mark_completed("bug-1")

        bug = queue_with_bug._bugs_by_id["bug-1"]
        assert bug.training_count == 1
        assert (
            bug.status == BugStatus.PENDING
        )  # Still pending (under max_training_uses)

    def test_mark_completed_sets_completed_when_max_reached(self, queue_with_bug):
        """Test that bug is marked completed when max training uses reached."""
        # Train 3 times (max_training_uses=3)
        for _ in range(3):
            queue_with_bug.mark_completed("bug-1")

        bug = queue_with_bug._bugs_by_id["bug-1"]
        assert bug.training_count == 3
        assert bug.status == BugStatus.COMPLETED

    def test_mark_completed_nonexistent_bug(self, queue_with_bug):
        """Test mark_completed with non-existent bug does nothing."""
        queue_with_bug.mark_completed("nonexistent")
        # No error should be raised


# =============================================================================
# Prune Stale Tests
# =============================================================================


class TestPruneStale:
    """Tests for prune_stale method."""

    def test_prune_stale_removes_old_bugs(self):
        """Test that prune_stale removes bugs older than staleness_days."""
        queue = HigherOrderQueue(staleness_days=30)

        # Add a bug with old last_accessed time
        from datetime import timedelta

        old_time = datetime.now(timezone.utc) - timedelta(days=45)
        bug = HigherOrderBug(
            bug_id="old-bug",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.MEDIUM,
            content_hash="hash-old",
            last_accessed=old_time,
        )
        queue._add_bug(bug)

        assert queue.get_queue_size() == 1

        pruned = queue.prune_stale()

        assert pruned == 1
        assert queue.get_queue_size() == 0
        assert queue._total_pruned == 1

    def test_prune_stale_keeps_recent_bugs(self):
        """Test that prune_stale keeps recent bugs."""
        queue = HigherOrderQueue(staleness_days=30)

        bug = HigherOrderBug(
            bug_id="new-bug",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.MEDIUM,
            content_hash="hash-new",
            # last_accessed defaults to now
        )
        queue._add_bug(bug)

        pruned = queue.prune_stale()

        assert pruned == 0
        assert queue.get_queue_size() == 1


# =============================================================================
# Internal Method Tests
# =============================================================================


class TestInternalMethods:
    """Tests for internal queue methods."""

    def test_add_bug(self):
        """Test _add_bug method."""
        queue = HigherOrderQueue()
        bug = HigherOrderBug(
            bug_id="bug-1",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.MEDIUM,
            content_hash="hash-1",
        )

        queue._add_bug(bug)

        assert queue.get_queue_size() == 1
        assert "bug-1" in queue._bugs_by_id
        assert queue._hash_index["hash-1"] == "bug-1"
        assert queue._difficulty_counts[5] == 1
        assert queue._total_added == 1

    def test_remove_bug(self):
        """Test _remove_bug method."""
        queue = HigherOrderQueue()
        bug = HigherOrderBug(
            bug_id="bug-1",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.MEDIUM,
            content_hash="hash-1",
        )
        queue._add_bug(bug)

        queue._remove_bug("bug-1")

        assert queue.get_queue_size() == 0
        assert "bug-1" not in queue._bugs_by_id
        assert "hash-1" not in queue._hash_index
        assert queue._difficulty_counts[5] == 0

    def test_evict_lowest_priority(self):
        """Test _evict_lowest_priority method."""
        queue = HigherOrderQueue(max_queue_size=2)

        # Add two bugs
        queue._add_bug(
            HigherOrderBug(
                bug_id="critical-bug",
                original_artifact_id="art-1",
                repository_id="repo-1",
                difficulty=8,
                priority=QueuePriority.CRITICAL,
                content_hash="hash-1",
            )
        )
        queue._add_bug(
            HigherOrderBug(
                bug_id="low-bug",
                original_artifact_id="art-2",
                repository_id="repo-1",
                difficulty=3,
                priority=QueuePriority.LOW,
                content_hash="hash-2",
            )
        )

        # This should evict the low priority bug
        queue._evict_lowest_priority()

        assert "critical-bug" in queue._bugs_by_id
        assert "low-bug" not in queue._bugs_by_id


# =============================================================================
# Bug Comparison Tests
# =============================================================================


class TestBugComparison:
    """Tests for bug comparison and ordering."""

    def test_same_priority_different_difficulty(self):
        """Test that higher difficulty wins for same priority."""
        high_diff = HigherOrderBug(
            bug_id="high-diff",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=9,
            priority=QueuePriority.MEDIUM,
        )
        low_diff = HigherOrderBug(
            bug_id="low-diff",
            original_artifact_id="art-2",
            repository_id="repo-1",
            difficulty=2,
            priority=QueuePriority.MEDIUM,
        )

        # Higher difficulty should be "less than" (higher priority in heap)
        assert high_diff < low_diff


# =============================================================================
# Metrics Tests
# =============================================================================


class TestMetrics:
    """Tests for queue metrics."""

    def test_metrics_with_bugs(self):
        """Test metrics with bugs in queue."""
        queue = HigherOrderQueue()

        # Add bugs at different priorities and difficulties
        queue._add_bug(
            HigherOrderBug(
                bug_id="bug-1",
                original_artifact_id="art-1",
                repository_id="repo-1",
                difficulty=5,
                priority=QueuePriority.CRITICAL,
                content_hash="hash-1",
            )
        )
        queue._add_bug(
            HigherOrderBug(
                bug_id="bug-2",
                original_artifact_id="art-2",
                repository_id="repo-1",
                difficulty=7,
                priority=QueuePriority.LOW,
                content_hash="hash-2",
            )
        )

        metrics = queue.get_metrics()

        assert metrics["queue_size"] == 2
        assert metrics["total_added"] == 2
        assert "CRITICAL" in metrics["priority_distribution"]
        assert "LOW" in metrics["priority_distribution"]
        assert metrics["difficulty_distribution"][5] == 1
        assert metrics["difficulty_distribution"][7] == 1


# =============================================================================
# Edge Case Tests for Full Coverage
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases to achieve full coverage."""

    def test_remove_nonexistent_bug(self):
        """Test _remove_bug with nonexistent bug_id."""
        queue = HigherOrderQueue()
        # Should not raise, just return silently
        queue._remove_bug("nonexistent-bug-id")
        assert queue.get_queue_size() == 0

    def test_evict_empty_queue(self):
        """Test _evict_lowest_priority on empty queue."""
        queue = HigherOrderQueue()
        # Should not raise, just return silently
        queue._evict_lowest_priority()
        assert queue.get_queue_size() == 0

    def test_add_bug_triggers_eviction(self):
        """Test that adding beyond max_queue_size triggers eviction."""
        queue = HigherOrderQueue(max_queue_size=2)

        # Add first bug (high priority)
        queue._add_bug(
            HigherOrderBug(
                bug_id="bug-1",
                original_artifact_id="art-1",
                repository_id="repo-1",
                difficulty=8,
                priority=QueuePriority.CRITICAL,
                content_hash="hash-1",
            )
        )

        # Add second bug (low priority)
        queue._add_bug(
            HigherOrderBug(
                bug_id="bug-2",
                original_artifact_id="art-2",
                repository_id="repo-1",
                difficulty=3,
                priority=QueuePriority.LOW,
                content_hash="hash-2",
            )
        )

        # Add third bug (medium priority) - should trigger eviction of low priority
        queue._add_bug(
            HigherOrderBug(
                bug_id="bug-3",
                original_artifact_id="art-3",
                repository_id="repo-1",
                difficulty=6,
                priority=QueuePriority.MEDIUM,
                content_hash="hash-3",
            )
        )

        # Low priority bug should have been evicted
        assert queue.get_queue_size() == 2
        assert "bug-1" in queue._bugs_by_id
        assert "bug-3" in queue._bugs_by_id
        assert "bug-2" not in queue._bugs_by_id

    def test_get_next_skips_removed_bugs(self):
        """Test that get_next skips bugs that were removed from _bugs_by_id."""
        queue = HigherOrderQueue()

        bug = HigherOrderBug(
            bug_id="bug-1",
            original_artifact_id="art-1",
            repository_id="repo-1",
            difficulty=5,
            priority=QueuePriority.MEDIUM,
            content_hash="hash-1",
        )
        queue._add_bug(bug)

        # Remove from _bugs_by_id but leave in heap
        del queue._bugs_by_id["bug-1"]

        # get_next should skip the removed bug and return None
        result = queue.get_next()
        assert result is None

    def test_deduplication_with_empty_patterns(self):
        """Test deduplication when one set of patterns is empty."""
        queue = HigherOrderQueue(similarity_threshold=0.7)

        # Add bug with patterns
        queue._add_bug(
            HigherOrderBug(
                bug_id="bug-1",
                original_artifact_id="art-1",
                repository_id="repo-1",
                difficulty=5,
                priority=QueuePriority.MEDIUM,
                content_hash="hash-1",
                error_patterns=["pattern1", "pattern2"],
            )
        )

        # Check deduplication with empty patterns
        from src.services.ssr.failure_analyzer import FailureAnalysis, FailureMode

        analysis_empty = FailureAnalysis(
            attempt_id="attempt-empty",
            artifact_id="art-empty",
            failure_mode=FailureMode.WRONG_FIX,
            error_patterns=[],  # Empty patterns
        )

        result = queue._check_duplicate("new-hash", [analysis_empty])
        assert result.is_duplicate is False

    def test_deduplication_fuzzy_match(self):
        """Test deduplication with fuzzy matching above threshold."""
        queue = HigherOrderQueue(similarity_threshold=0.5)

        # Add bug with specific patterns
        queue._add_bug(
            HigherOrderBug(
                bug_id="bug-1",
                original_artifact_id="art-1",
                repository_id="repo-1",
                difficulty=5,
                priority=QueuePriority.MEDIUM,
                content_hash="hash-1",
                error_patterns=[
                    "null pointer",
                    "divide by zero",
                    "index out of bounds",
                ],
            )
        )

        # Check with overlapping patterns (should match)
        from src.services.ssr.failure_analyzer import FailureAnalysis, FailureMode

        analysis_similar = FailureAnalysis(
            attempt_id="attempt-similar",
            artifact_id="art-similar",
            failure_mode=FailureMode.WRONG_FIX,
            error_patterns=["null pointer", "divide by zero"],  # 2/3 overlap
        )

        result = queue._check_duplicate("different-hash", [analysis_similar])
        # Jaccard similarity = 2/3 = 0.667 > 0.5 threshold
        assert result.is_duplicate is True
        assert result.duplicate_of == "bug-1"
        assert result.similarity_score >= 0.5

    def test_priority_high_difficulty(self):
        """Test priority calculation for high difficulty bugs."""
        queue = HigherOrderQueue()

        from src.services.ssr.failure_analyzer import (
            FailureAnalysis,
            FailureMode,
            FailureSummary,
            LearningSignalType,
        )

        # High difficulty (>= 7) should get HIGH priority
        summary = FailureSummary(
            artifact_id="art-high-diff",
            total_attempts=3,
            failure_modes={FailureMode.WRONG_FIX: 2},
            learning_signals={LearningSignalType.LOGIC_ERROR: 1},
            avg_difficulty_delta=1.0,  # Low delta to not trigger MEDIUM
            is_higher_order_candidate=True,
            recommended_difficulty=8,  # High difficulty
        )

        analysis = FailureAnalysis(
            attempt_id="attempt-1",
            artifact_id="art-high-diff",
            failure_mode=FailureMode.WRONG_FIX,
            error_patterns=["unique pattern 123"],
        )

        bug = queue.add_from_failure(
            summary=summary,
            analyses=[analysis],
            repository_id="repo-1",
        )

        assert bug is not None
        # High difficulty (>= 7) should result in HIGH priority
        assert bug.priority in (QueuePriority.HIGH, QueuePriority.CRITICAL)

    def test_priority_semantic_errors(self):
        """Test priority calculation with consistent semantic errors."""
        queue = HigherOrderQueue()

        from src.services.ssr.failure_analyzer import (
            FailureAnalysis,
            FailureMode,
            FailureSummary,
            LearningSignalType,
        )

        # Create summary with semantic errors
        summary = FailureSummary(
            artifact_id="art-semantic",
            total_attempts=10,
            failure_modes={FailureMode.SEMANTIC_ERROR: 8, FailureMode.WRONG_FIX: 2},
            learning_signals={LearningSignalType.LOGIC_ERROR: 5},
            avg_difficulty_delta=1.0,
            is_higher_order_candidate=True,
            recommended_difficulty=5,  # Not high difficulty
        )

        # 80% semantic errors (>= 70% threshold for HIGH priority)
        analyses = [
            FailureAnalysis(
                attempt_id=f"attempt-{i}",
                artifact_id="art-semantic",
                failure_mode=FailureMode.SEMANTIC_ERROR,
                error_patterns=[f"semantic error pattern {i}"],
            )
            for i in range(8)
        ] + [
            FailureAnalysis(
                attempt_id="attempt-wrong",
                artifact_id="art-semantic",
                failure_mode=FailureMode.WRONG_FIX,
                error_patterns=["wrong fix pattern"],
            )
        ]

        bug = queue.add_from_failure(
            summary=summary,
            analyses=analyses,
            repository_id="repo-1",
        )

        assert bug is not None
        # 80% semantic errors should give HIGH priority
        assert bug.priority == QueuePriority.HIGH

    def test_priority_low_delta(self):
        """Test priority calculation with low difficulty delta (LOW priority)."""
        queue = HigherOrderQueue()

        from src.services.ssr.failure_analyzer import (
            FailureAnalysis,
            FailureMode,
            FailureSummary,
            LearningSignalType,
        )

        # Low delta, low difficulty, not semantic errors -> LOW priority
        summary = FailureSummary(
            artifact_id="art-low",
            total_attempts=3,
            failure_modes={FailureMode.PARTIAL_FIX: 3},
            learning_signals={LearningSignalType.EDGE_CASE_MISSED: 1},
            avg_difficulty_delta=1.0,  # Low delta (< 2)
            is_higher_order_candidate=True,
            recommended_difficulty=3,  # Low difficulty (< 7)
        )

        analysis = FailureAnalysis(
            attempt_id="attempt-low",
            artifact_id="art-low",
            failure_mode=FailureMode.PARTIAL_FIX,
            error_patterns=["low priority pattern"],
        )

        bug = queue.add_from_failure(
            summary=summary,
            analyses=[analysis],
            repository_id="repo-1",
        )

        assert bug is not None
        assert bug.priority == QueuePriority.LOW

    def test_priority_medium_delta(self):
        """Test priority calculation with medium difficulty delta (MEDIUM priority)."""
        queue = HigherOrderQueue()

        from src.services.ssr.failure_analyzer import (
            FailureAnalysis,
            FailureMode,
            FailureSummary,
            LearningSignalType,
        )

        # Medium delta (>= 2), low difficulty, not semantic errors -> MEDIUM priority
        summary = FailureSummary(
            artifact_id="art-medium",
            total_attempts=3,
            failure_modes={FailureMode.PARTIAL_FIX: 3},
            learning_signals={LearningSignalType.SCOPE_ERROR: 1},
            avg_difficulty_delta=3.0,  # Medium delta (>= 2)
            is_higher_order_candidate=True,
            recommended_difficulty=4,  # Low difficulty (< 7)
        )

        analysis = FailureAnalysis(
            attempt_id="attempt-medium",
            artifact_id="art-medium",
            failure_mode=FailureMode.PARTIAL_FIX,
            error_patterns=["medium priority pattern xyz"],
        )

        bug = queue.add_from_failure(
            summary=summary,
            analyses=[analysis],
            repository_id="repo-1",
        )

        assert bug is not None
        assert bug.priority == QueuePriority.MEDIUM

    def test_priority_high_difficulty_not_timeout(self):
        """Test priority HIGH for high difficulty without timeout or semantic errors."""
        queue = HigherOrderQueue()

        from src.services.ssr.failure_analyzer import (
            FailureAnalysis,
            FailureMode,
            FailureSummary,
            LearningSignalType,
        )

        # High difficulty (>= 7), no timeout, no semantic errors -> HIGH priority
        # Use PARTIAL_FIX which is NOT counted as semantic error
        summary = FailureSummary(
            artifact_id="art-high-no-timeout",
            total_attempts=3,
            failure_modes={FailureMode.PARTIAL_FIX: 3},  # Not semantic
            learning_signals={LearningSignalType.LOGIC_ERROR: 1},
            avg_difficulty_delta=1.0,  # Low delta
            is_higher_order_candidate=True,
            recommended_difficulty=7,  # Exactly 7 (threshold)
        )

        # Analysis with PARTIAL_FIX (not timeout, not semantic_error, not wrong_fix)
        analysis = FailureAnalysis(
            attempt_id="attempt-high-no-timeout",
            artifact_id="art-high-no-timeout",
            failure_mode=FailureMode.PARTIAL_FIX,
            error_patterns=["unique pattern abc123 high diff"],
        )

        bug = queue.add_from_failure(
            summary=summary,
            analyses=[analysis],
            repository_id="repo-1",
        )

        assert bug is not None
        # High difficulty without timeout or semantic errors should be HIGH
        assert bug.priority == QueuePriority.HIGH
