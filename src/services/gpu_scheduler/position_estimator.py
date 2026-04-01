"""Queue position estimator for GPU job scheduling.

Estimates queue position and wait time per ADR-061 Phase 2.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.services.gpu_scheduler.models import (
    GPUJobPriority,
    GPUJobType,
    PositionEstimate,
)

if TYPE_CHECKING:
    from src.services.gpu_scheduler.queue_engine import GPUQueueEngine

logger = logging.getLogger(__name__)

# Average job durations by type (in minutes) - from ADR-061
DEFAULT_DURATION_MINUTES: dict[GPUJobType, int] = {
    GPUJobType.EMBEDDING_GENERATION: 30,
    GPUJobType.LOCAL_INFERENCE: 60,  # Continuous, estimate session length
    GPUJobType.VULNERABILITY_TRAINING: 120,
    GPUJobType.SWE_RL_TRAINING: 240,
    GPUJobType.MEMORY_CONSOLIDATION: 10,
}

# GPU scaling time estimate (from 0 to 1 node)
GPU_SCALING_TIME_MINUTES = 5

# Priority concurrent limits from ADR-061
PRIORITY_CONCURRENT_LIMITS: dict[GPUJobPriority, int] = {
    GPUJobPriority.HIGH: 2,
    GPUJobPriority.NORMAL: 4,
    GPUJobPriority.LOW: 2,
}


class PositionEstimator:
    """Estimates queue position and expected wait time for GPU jobs.

    Factors considered:
    1. Jobs ahead in queue by priority
    2. Average job duration by type
    3. GPU autoscaling time (when scaling from 0)
    4. Concurrent job limits per priority
    5. Starvation promotion timing
    """

    def __init__(
        self,
        queue_engine: GPUQueueEngine | None = None,
        duration_estimates: dict[GPUJobType, int] | None = None,
        gpu_scaling_time_minutes: int = GPU_SCALING_TIME_MINUTES,
    ):
        """Initialize the estimator.

        Args:
            queue_engine: Queue engine to query for position data.
            duration_estimates: Custom job duration estimates by type.
            gpu_scaling_time_minutes: Time to scale GPU nodes from 0.
        """
        self.queue_engine = queue_engine
        self.duration_estimates = duration_estimates or DEFAULT_DURATION_MINUTES
        self.gpu_scaling_time = timedelta(minutes=gpu_scaling_time_minutes)

    def estimate_position(
        self,
        job_id: str,
        current_gpu_count: int = 0,
        scaling_in_progress: bool = False,
    ) -> PositionEstimate:
        """Estimate queue position and wait time for a queued job.

        Args:
            job_id: Job to estimate for.
            current_gpu_count: Current number of available GPUs.
            scaling_in_progress: Whether cluster is scaling up.

        Returns:
            PositionEstimate with detailed breakdown.
        """
        if self.queue_engine is None:
            raise ValueError("Queue engine not configured")

        now = datetime.now(timezone.utc)
        factors: list[str] = []

        # Get queue position
        position = self.queue_engine.get_queue_position(job_id)
        if position is None:
            # Job not in queue - return immediate estimate
            return PositionEstimate(
                job_id=job_id,
                queue_position=0,
                jobs_ahead=0,
                jobs_ahead_by_priority={p.value: 0 for p in GPUJobPriority},
                estimated_wait_minutes=0,
                estimated_start_time=now,
                confidence=1.0,
                factors=["Job not in queue or already running"],
                gpu_scaling_required=False,
                preemption_possible=False,
            )

        # Get jobs ahead
        jobs_ahead_by_priority = self._count_jobs_ahead(job_id)
        jobs_ahead = sum(jobs_ahead_by_priority.values())

        # Calculate estimated wait time
        wait_minutes, wait_factors = self._estimate_wait_time(
            jobs_ahead_by_priority,
            current_gpu_count,
            scaling_in_progress,
        )
        factors.extend(wait_factors)

        # Calculate confidence
        confidence = self._calculate_confidence(jobs_ahead, factors)

        # Determine if preemption is possible
        job = self.queue_engine._jobs_by_id.get(job_id)
        preemption_possible = (
            job is not None
            and job.priority == GPUJobPriority.HIGH
            and len(self.queue_engine.get_preemptable_jobs()) > 0
        )

        if preemption_possible:
            factors.append("Preemption possible (HIGH priority with LOW running)")

        estimated_start = now + timedelta(minutes=wait_minutes)

        return PositionEstimate(
            job_id=job_id,
            queue_position=position,
            jobs_ahead=jobs_ahead,
            jobs_ahead_by_priority=jobs_ahead_by_priority,
            estimated_wait_minutes=wait_minutes,
            estimated_start_time=estimated_start,
            confidence=confidence,
            factors=factors,
            gpu_scaling_required=current_gpu_count == 0,
            preemption_possible=preemption_possible,
        )

    def estimate_for_new_job(
        self,
        priority: GPUJobPriority,
        job_type: GPUJobType,
        organization_id: str,
        current_gpu_count: int = 0,
    ) -> PositionEstimate:
        """Estimate position for a job before it's submitted.

        Used by the Schedule Job modal to show estimated wait time.

        Args:
            priority: Priority of the potential job.
            job_type: Type of the potential job.
            organization_id: Organization submitting the job.
            current_gpu_count: Current number of available GPUs.

        Returns:
            PositionEstimate for the potential job.
        """
        now = datetime.now(timezone.utc)
        factors: list[str] = []

        if self.queue_engine is None:
            # Return default estimate without queue data
            wait_minutes = 0
            if current_gpu_count == 0:
                wait_minutes = int(self.gpu_scaling_time.total_seconds() / 60)
                factors.append("GPU scaling required from 0")

            return PositionEstimate(
                job_id="estimate",
                queue_position=1,
                jobs_ahead=0,
                jobs_ahead_by_priority={p.value: 0 for p in GPUJobPriority},
                estimated_wait_minutes=wait_minutes,
                estimated_start_time=now + timedelta(minutes=wait_minutes),
                confidence=0.5,
                factors=factors or ["Queue engine not available"],
                gpu_scaling_required=current_gpu_count == 0,
                preemption_possible=False,
            )

        # Simulate adding job to queue
        metrics = self.queue_engine.get_metrics()

        # Count jobs that would be ahead of this one
        jobs_ahead_by_priority: dict[str, int] = {}

        for p in GPUJobPriority:
            # Jobs with higher or equal priority that are already queued
            if self._priority_value(p) <= self._priority_value(priority):
                jobs_ahead_by_priority[p.value] = metrics.by_priority.get(p.value, 0)
            else:
                jobs_ahead_by_priority[p.value] = 0

        jobs_ahead = sum(jobs_ahead_by_priority.values())

        # Estimate queue position
        position = jobs_ahead + 1

        # Calculate wait time
        wait_minutes, wait_factors = self._estimate_wait_time(
            jobs_ahead_by_priority,
            current_gpu_count,
            scaling_in_progress=False,
        )
        factors.extend(wait_factors)

        # Check if this job could preempt
        preemption_possible = (
            priority == GPUJobPriority.HIGH
            and len(self.queue_engine.get_preemptable_jobs()) > 0
        )

        if preemption_possible:
            factors.append("May preempt LOW priority job")
            wait_minutes = max(0, wait_minutes - 30)  # Reduce estimate

        # Calculate confidence
        confidence = self._calculate_confidence(jobs_ahead, factors)

        return PositionEstimate(
            job_id="estimate",
            queue_position=position,
            jobs_ahead=jobs_ahead,
            jobs_ahead_by_priority=jobs_ahead_by_priority,
            estimated_wait_minutes=wait_minutes,
            estimated_start_time=now + timedelta(minutes=wait_minutes),
            confidence=confidence,
            factors=factors,
            gpu_scaling_required=current_gpu_count == 0,
            preemption_possible=preemption_possible,
        )

    def _count_jobs_ahead(self, job_id: str) -> dict[str, int]:
        """Count jobs ahead of this job by priority.

        Args:
            job_id: Job to count ahead of.

        Returns:
            Dict mapping priority to count of jobs ahead.
        """
        if self.queue_engine is None:
            return {p.value: 0 for p in GPUJobPriority}

        target_job = self.queue_engine._jobs_by_id.get(job_id)
        if target_job is None:
            return {p.value: 0 for p in GPUJobPriority}

        target_key = target_job.priority_key()

        counts: dict[str, int] = {p.value: 0 for p in GPUJobPriority}

        for job in self.queue_engine._heap:
            if job.job_id not in self.queue_engine._jobs_by_id:
                continue
            if job.job_id == job_id:
                continue
            if job.priority_key() < target_key:
                counts[job.priority.value] += 1

        return counts

    def _estimate_wait_time(
        self,
        jobs_ahead_by_priority: dict[str, int],
        current_gpu_count: int,
        scaling_in_progress: bool,
    ) -> tuple[int, list[str]]:
        """Estimate wait time based on jobs ahead.

        Args:
            jobs_ahead_by_priority: Jobs ahead by priority level.
            current_gpu_count: Current GPU count.
            scaling_in_progress: Whether scaling is in progress.

        Returns:
            Tuple of (wait_minutes, factors).
        """
        factors: list[str] = []
        total_minutes = 0

        # Add GPU scaling time if needed
        if current_gpu_count == 0 and not scaling_in_progress:
            scaling_minutes = int(self.gpu_scaling_time.total_seconds() / 60)
            total_minutes += scaling_minutes
            factors.append(f"GPU scaling from 0: +{scaling_minutes} min")

        # Calculate wait time for jobs ahead
        for priority_str, count in jobs_ahead_by_priority.items():
            if count == 0:
                continue

            priority = GPUJobPriority(priority_str)
            concurrent_limit = PRIORITY_CONCURRENT_LIMITS.get(priority, 2)

            # Average duration (use 30 min default)
            avg_duration = 30

            # Batches needed = ceil(count / concurrent_limit)
            batches = (count + concurrent_limit - 1) // concurrent_limit
            wait_for_priority = batches * avg_duration

            total_minutes += wait_for_priority
            factors.append(
                f"{count} {priority_str} jobs ahead: +{wait_for_priority} min"
            )

        return total_minutes, factors

    def _calculate_confidence(
        self,
        jobs_ahead: int,
        factors: list[str],
    ) -> float:
        """Calculate confidence score for the estimate.

        Lower confidence when:
        - Many jobs ahead
        - GPU scaling in progress
        - Mixed job types (variable durations)

        Args:
            jobs_ahead: Number of jobs ahead.
            factors: Factors affecting estimate.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        confidence = 1.0

        # Reduce confidence for more jobs ahead
        if jobs_ahead > 0:
            confidence -= min(0.3, jobs_ahead * 0.05)

        # Reduce confidence for GPU scaling
        if any("scaling" in f.lower() for f in factors):
            confidence -= 0.1

        # Reduce confidence for preemption possibility
        if any("preempt" in f.lower() for f in factors):
            confidence -= 0.15

        return max(0.1, confidence)

    def _priority_value(self, priority: GPUJobPriority) -> int:
        """Get numeric value for priority comparison.

        Lower value = higher priority.

        Args:
            priority: Priority to convert.

        Returns:
            Numeric priority value.
        """
        return {
            GPUJobPriority.HIGH: 1,
            GPUJobPriority.NORMAL: 2,
            GPUJobPriority.LOW: 3,
        }.get(priority, 2)


# Singleton instance
_position_estimator: PositionEstimator | None = None


def get_position_estimator() -> PositionEstimator:
    """Get or create the position estimator singleton."""
    global _position_estimator
    if _position_estimator is None:
        _position_estimator = PositionEstimator()
    return _position_estimator


def init_position_estimator(
    queue_engine: GPUQueueEngine,
) -> PositionEstimator:
    """Initialize the position estimator with dependencies.

    Args:
        queue_engine: Queue engine for position queries.

    Returns:
        Initialized PositionEstimator.
    """
    global _position_estimator
    _position_estimator = PositionEstimator(queue_engine=queue_engine)
    return _position_estimator
