"""Priority queue engine for GPU job scheduling.

Implements priority-based queue management with fairness scheduling
per ADR-061 Phase 2.
"""

from __future__ import annotations

import heapq
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.services.gpu_scheduler.models import (
    GPUJob,
    GPUJobPriority,
    QueuedJob,
    QueueMetrics,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Priority limits from ADR-061
PRIORITY_LIMITS: dict[GPUJobPriority, dict] = {
    GPUJobPriority.HIGH: {
        "max_concurrent": 2,
        "can_preempt": True,
        "can_be_preempted": False,
    },
    GPUJobPriority.NORMAL: {
        "max_concurrent": 4,
        "can_preempt": False,
        "can_be_preempted": False,
    },
    GPUJobPriority.LOW: {
        "max_concurrent": 2,
        "can_preempt": False,
        "can_be_preempted": True,
    },
}

# Starvation prevention threshold (30 minutes per ADR-061)
STARVATION_THRESHOLD_MINUTES = 30


class GPUQueueEngine:
    """Priority queue engine with fairness scheduling for GPU jobs.

    Implements:
    - Priority-weighted scheduling (HIGH > NORMAL > LOW)
    - Per-priority concurrent job limits
    - Organization fairness via round-robin within same priority
    - Starvation prevention via automatic priority promotion

    Based on the pattern from src/services/ssr/higher_order_queue.py.
    """

    def __init__(
        self,
        starvation_threshold_minutes: int = STARVATION_THRESHOLD_MINUTES,
        priority_limits: dict[GPUJobPriority, dict] | None = None,
    ):
        """Initialize the queue engine.

        Args:
            starvation_threshold_minutes: Minutes before LOW priority jobs
                are promoted to prevent starvation.
            priority_limits: Custom priority limits (defaults to ADR-061 spec).
        """
        # Priority queue (min-heap)
        self._heap: list[QueuedJob] = []

        # Index for O(1) job lookup
        self._jobs_by_id: dict[str, QueuedJob] = {}

        # Track running jobs for concurrent limit enforcement
        self._running_by_priority: dict[GPUJobPriority, set[str]] = {
            GPUJobPriority.HIGH: set(),
            GPUJobPriority.NORMAL: set(),
            GPUJobPriority.LOW: set(),
        }

        # Track running jobs by organization for fairness
        self._running_by_org: dict[str, set[str]] = defaultdict(set)

        # Track last dispatch time per organization for round-robin
        self._org_last_dispatch: dict[str, datetime] = {}

        # Configuration
        self.starvation_threshold = timedelta(minutes=starvation_threshold_minutes)
        self.priority_limits = priority_limits or PRIORITY_LIMITS

        # Metrics tracking
        self._total_wait_time_seconds: float = 0.0
        self._completed_jobs_count: int = 0
        self._preemptions_timestamps: list[datetime] = []
        self._promotion_timestamps: list[datetime] = []

    def enqueue(self, job: GPUJob) -> QueuedJob:
        """Add a job to the priority queue.

        Args:
            job: GPUJob to enqueue.

        Returns:
            QueuedJob with scheduling metadata.
        """
        now = datetime.now(timezone.utc)

        # Create queued job with metadata
        queued_job = QueuedJob.from_gpu_job(job, queued_at=now)

        # Add to heap and index
        heapq.heappush(self._heap, queued_job)
        self._jobs_by_id[job.job_id] = queued_job

        logger.info(
            "Enqueued GPU job",
            extra={
                "job_id": job.job_id,
                "priority": job.priority.value,
                "organization_id": job.organization_id,
                "queue_size": len(self._heap),
            },
        )

        return queued_job

    def dequeue(self) -> QueuedJob | None:
        """Get the next job to execute respecting priority and fairness.

        Algorithm:
        1. Promote starved jobs first
        2. Pop from heap (sorted by priority_key)
        3. Check concurrent limits
        4. Return first job that can run, or None if at capacity

        Returns:
            Next QueuedJob to execute, or None if queue is empty or at capacity.
        """
        # Promote starved jobs before processing
        self.promote_starved_jobs()

        # Process candidates from the heap
        candidates_to_requeue: list[QueuedJob] = []

        while self._heap:
            candidate = heapq.heappop(self._heap)

            # Skip if job was removed (cancelled)
            if candidate.job_id not in self._jobs_by_id:
                continue

            priority = candidate.priority

            # Check if we can start this job within concurrent limits
            if self.can_start_job(priority):
                # Remove from index
                del self._jobs_by_id[candidate.job_id]

                # Update wait time metrics
                now = datetime.now(timezone.utc)
                wait_seconds = (now - candidate.queued_at).total_seconds()
                candidate.wait_time_seconds = wait_seconds
                self._total_wait_time_seconds += wait_seconds
                self._completed_jobs_count += 1

                # Update org last dispatch for round-robin
                self._org_last_dispatch[candidate.organization_id] = now

                # Re-add candidates that couldn't run
                for job in candidates_to_requeue:
                    heapq.heappush(self._heap, job)

                logger.info(
                    "Dequeued GPU job",
                    extra={
                        "job_id": candidate.job_id,
                        "priority": priority.value,
                        "wait_seconds": wait_seconds,
                    },
                )

                return candidate

            # Can't run this job, save for re-queue
            candidates_to_requeue.append(candidate)

        # Re-add all candidates that couldn't run
        for job in candidates_to_requeue:
            heapq.heappush(self._heap, job)

        return None

    def remove(self, job_id: str) -> QueuedJob | None:
        """Remove a job from the queue (for cancellation).

        Args:
            job_id: ID of job to remove.

        Returns:
            Removed QueuedJob, or None if not found.
        """
        if job_id not in self._jobs_by_id:
            return None

        job = self._jobs_by_id.pop(job_id)

        # Note: We don't remove from heap immediately (lazy deletion)
        # The job will be skipped when encountered during dequeue

        logger.info(
            "Removed GPU job from queue",
            extra={"job_id": job_id, "priority": job.priority.value},
        )

        return job

    def peek(self, count: int = 10) -> list[QueuedJob]:
        """Peek at the top N jobs without removing them.

        Args:
            count: Maximum number of jobs to return.

        Returns:
            List of top QueuedJobs in priority order.
        """
        import heapq

        # Use heapq.nsmallest for O(n log k) instead of O(n log n) full sort
        active_jobs = [j for j in self._heap if j.job_id in self._jobs_by_id]
        return heapq.nsmallest(count, active_jobs, key=lambda j: j.priority_key())

    def get_queue_position(self, job_id: str) -> int | None:
        """Get the current queue position for a job.

        Args:
            job_id: Job ID to find position for.

        Returns:
            Position (1-indexed), or None if job not in queue.
        """
        if job_id not in self._jobs_by_id:
            return None

        target_job = self._jobs_by_id[job_id]
        target_key = target_job.priority_key()

        position = 1
        for job in self._heap:
            if job.job_id not in self._jobs_by_id:
                continue
            if job.job_id == job_id:
                break
            if job.priority_key() < target_key:
                position += 1

        return position

    def promote_starved_jobs(self) -> list[str]:
        """Promote LOW priority jobs waiting longer than starvation threshold.

        Per ADR-061: LOW priority jobs are promoted after 30 min wait.

        Returns:
            List of job IDs that were promoted.
        """
        now = datetime.now(timezone.utc)
        promoted_ids: list[str] = []

        for job in self._heap:
            if job.job_id not in self._jobs_by_id:
                continue

            # Only promote LOW priority, non-promoted jobs
            if job.priority != GPUJobPriority.LOW or job.starvation_promoted:
                continue

            wait_time = now - job.queued_at
            if wait_time >= self.starvation_threshold:
                job.starvation_promoted = True
                job.promotion_time = now
                promoted_ids.append(job.job_id)
                self._promotion_timestamps.append(now)

                logger.info(
                    "Promoted starved GPU job",
                    extra={
                        "job_id": job.job_id,
                        "wait_minutes": wait_time.total_seconds() / 60,
                    },
                )

        # Re-heapify if any jobs were promoted
        if promoted_ids:
            heapq.heapify(self._heap)

        return promoted_ids

    def mark_job_running(
        self,
        job_id: str,
        priority: GPUJobPriority,
        organization_id: str,
    ) -> None:
        """Mark a job as running for concurrent limit tracking.

        Args:
            job_id: Job ID to mark as running.
            priority: Priority level of the job.
            organization_id: Organization that owns the job.
        """
        self._running_by_priority[priority].add(job_id)
        self._running_by_org[organization_id].add(job_id)

        logger.debug(
            "Marked job running",
            extra={
                "job_id": job_id,
                "priority": priority.value,
                "running_count": len(self._running_by_priority[priority]),
            },
        )

    def mark_job_completed(
        self,
        job_id: str,
        priority: GPUJobPriority,
        organization_id: str,
    ) -> None:
        """Mark a job as completed (decrement concurrent count).

        Args:
            job_id: Job ID to mark as completed.
            priority: Priority level of the job.
            organization_id: Organization that owns the job.
        """
        self._running_by_priority[priority].discard(job_id)
        self._running_by_org[organization_id].discard(job_id)

        logger.debug(
            "Marked job completed",
            extra={
                "job_id": job_id,
                "priority": priority.value,
                "running_count": len(self._running_by_priority[priority]),
            },
        )

    def can_start_job(self, priority: GPUJobPriority) -> bool:
        """Check if a job of this priority can start within concurrent limits.

        Args:
            priority: Priority level to check.

        Returns:
            True if a job can start, False if at capacity.
        """
        max_concurrent = self.priority_limits[priority]["max_concurrent"]
        current = len(self._running_by_priority[priority])
        return current < max_concurrent

    def get_running_count(self, priority: GPUJobPriority) -> int:
        """Get count of running jobs at a priority level.

        Args:
            priority: Priority level to check.

        Returns:
            Number of running jobs.
        """
        return len(self._running_by_priority[priority])

    def find_preemption_candidate(self, priority: GPUJobPriority) -> str | None:
        """Find a running job that can be preempted for a higher-priority job.

        Per ADR-061: Only HIGH priority can preempt, and only LOW priority
        jobs can be preempted.

        Args:
            priority: Priority of the job wanting to run.

        Returns:
            job_id of preemption candidate, or None if no candidate.
        """
        # Only HIGH priority can preempt
        if not self.priority_limits[priority]["can_preempt"]:
            return None

        # Find a LOW priority job that can be preempted
        low_running = self._running_by_priority[GPUJobPriority.LOW]
        if not low_running:
            return None

        # Return the first (any) LOW priority running job
        # In a more sophisticated implementation, we could pick the one
        # with most progress to minimize wasted work
        return next(iter(low_running))

    def get_preemptable_jobs(self) -> list[str]:
        """Get all job IDs that can be preempted.

        Returns:
            List of job IDs that can be preempted.
        """
        return list(self._running_by_priority[GPUJobPriority.LOW])

    def get_metrics(self) -> QueueMetrics:
        """Get current queue metrics.

        Returns:
            QueueMetrics with current statistics.
        """
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        # Count queued jobs by priority
        by_priority: dict[str, int] = {p.value: 0 for p in GPUJobPriority}
        by_organization: dict[str, int] = defaultdict(int)
        oldest_queued_at: datetime | None = None

        for job in self._heap:
            if job.job_id not in self._jobs_by_id:
                continue
            by_priority[job.priority.value] += 1
            by_organization[job.organization_id] += 1

            if oldest_queued_at is None or job.queued_at < oldest_queued_at:
                oldest_queued_at = job.queued_at

        # Count running jobs
        running_by_priority = {
            p.value: len(jobs) for p, jobs in self._running_by_priority.items()
        }
        total_running = sum(running_by_priority.values())

        # Calculate average wait time
        avg_wait = 0.0
        if self._completed_jobs_count > 0:
            avg_wait = self._total_wait_time_seconds / self._completed_jobs_count

        # Count recent preemptions and promotions
        preemptions_last_hour = sum(
            1 for t in self._preemptions_timestamps if t >= one_hour_ago
        )
        promotions_last_hour = sum(
            1 for t in self._promotion_timestamps if t >= one_hour_ago
        )

        # Clean up old timestamps
        self._preemptions_timestamps = [
            t for t in self._preemptions_timestamps if t >= one_hour_ago
        ]
        self._promotion_timestamps = [
            t for t in self._promotion_timestamps if t >= one_hour_ago
        ]

        total_queued = sum(by_priority.values())

        return QueueMetrics(
            total_queued=total_queued,
            by_priority=by_priority,
            by_organization=dict(by_organization),
            running_jobs=total_running,
            running_by_priority=running_by_priority,
            avg_wait_time_seconds=avg_wait,
            oldest_queued_at=oldest_queued_at,
            estimated_drain_time_minutes=self._estimate_drain_time(total_queued),
            preemptions_last_hour=preemptions_last_hour,
            starvation_promotions_last_hour=promotions_last_hour,
        )

    def _estimate_drain_time(self, queue_depth: int) -> int:
        """Estimate time to drain the queue in minutes.

        Simple estimation based on average job duration and concurrent limits.

        Args:
            queue_depth: Number of jobs in queue.

        Returns:
            Estimated minutes to drain queue.
        """
        if queue_depth == 0:
            return 0

        # Average job duration assumption (30 minutes)
        avg_job_minutes = 30

        # Total concurrent capacity
        total_capacity = sum(
            limits["max_concurrent"] for limits in self.priority_limits.values()
        )

        if total_capacity == 0:
            return 0

        # Estimate: (queue_depth / concurrent_capacity) * avg_duration
        return int((queue_depth / total_capacity) * avg_job_minutes)

    def record_preemption(self) -> None:
        """Record a preemption event for metrics."""
        self._preemptions_timestamps.append(datetime.now(timezone.utc))

    def size(self) -> int:
        """Get number of jobs in queue."""
        return len(self._jobs_by_id)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._jobs_by_id) == 0

    def clear(self) -> None:
        """Clear all jobs from the queue."""
        self._heap.clear()
        self._jobs_by_id.clear()
        for priority in self._running_by_priority:
            self._running_by_priority[priority].clear()
        self._running_by_org.clear()
        self._org_last_dispatch.clear()

        logger.info("Cleared GPU job queue")


# Singleton instance
_queue_engine: GPUQueueEngine | None = None


def get_queue_engine() -> GPUQueueEngine:
    """Get or create the queue engine singleton."""
    global _queue_engine
    if _queue_engine is None:
        _queue_engine = GPUQueueEngine()
    return _queue_engine
