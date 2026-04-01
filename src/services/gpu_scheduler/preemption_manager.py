"""Preemption manager for GPU job scheduling.

Handles job preemption with checkpoint coordination per ADR-061 Phase 2.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.services.gpu_scheduler.exceptions import CheckpointError, PreemptionError
from src.services.gpu_scheduler.models import (
    GPUJob,
    GPUJobPriority,
    PreemptionEvent,
    PreemptionReason,
)

if TYPE_CHECKING:
    from src.services.gpu_scheduler.k8s_client import GPUJobK8sClient

logger = logging.getLogger(__name__)

# Default timeout for checkpoint operations
CHECKPOINT_TIMEOUT_SECONDS = 300  # 5 minutes


class PreemptionManager:
    """Manages job preemption for high-priority GPU workloads.

    Preemption workflow:
    1. Signal running job to save checkpoint (via pod annotation)
    2. Wait for checkpoint confirmation (with timeout)
    3. Terminate the Kubernetes job
    4. Re-queue the preempted job with priority boost
    5. Start the high-priority job

    Per ADR-061:
    - HIGH priority can preempt LOW priority
    - NORMAL priority cannot be preempted
    - Preempted LOW jobs are boosted to NORMAL when re-queued
    """

    def __init__(
        self,
        k8s_client: GPUJobK8sClient | None = None,
        s3_client=None,
        checkpoint_timeout_seconds: int = CHECKPOINT_TIMEOUT_SECONDS,
        priority_boost_on_preemption: bool = True,
    ):
        """Initialize the preemption manager.

        Args:
            k8s_client: Kubernetes client for job management.
            s3_client: S3 client for checkpoint verification.
            checkpoint_timeout_seconds: Timeout for checkpoint operations.
            priority_boost_on_preemption: Whether to boost priority of
                preempted jobs when re-queued.
        """
        self.k8s_client = k8s_client
        self.s3_client = s3_client
        self.checkpoint_timeout = checkpoint_timeout_seconds
        self.priority_boost = priority_boost_on_preemption

    async def preempt_job(
        self,
        preempting_job: GPUJob,
        preempted_job: GPUJob,
        reason: PreemptionReason = PreemptionReason.HIGH_PRIORITY_JOB,
    ) -> PreemptionEvent:
        """Preempt a running job to make room for a higher-priority job.

        Args:
            preempting_job: The high-priority job that needs to run.
            preempted_job: The running job to preempt.
            reason: Reason for preemption.

        Returns:
            PreemptionEvent with details.

        Raises:
            PreemptionError: If preemption fails.
        """
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        logger.info(
            "Starting job preemption",
            extra={
                "event_id": event_id,
                "preempting_job_id": preempting_job.job_id,
                "preempted_job_id": preempted_job.job_id,
                "reason": reason.value,
            },
        )

        # Validate preemption is allowed
        if not self._can_preempt(preempting_job.priority, preempted_job.priority):
            raise PreemptionError(
                preempted_job.job_id,
                preempting_job.job_id,
                f"Cannot preempt {preempted_job.priority.value} priority job "
                f"for {preempting_job.priority.value} priority job",
            )

        checkpoint_saved = False
        checkpoint_s3_path = None

        # Try to save checkpoint if enabled
        if preempted_job.checkpoint_enabled:
            try:
                checkpoint_saved = await self._signal_and_wait_checkpoint(preempted_job)
                if checkpoint_saved:
                    checkpoint_s3_path = preempted_job.checkpoint_s3_path
            except (CheckpointError, asyncio.TimeoutError) as e:
                logger.warning(f"Checkpoint failed for job {preempted_job.job_id}: {e}")
                # Continue with preemption even if checkpoint fails

        # Terminate the Kubernetes job
        try:
            await self._terminate_k8s_job(preempted_job)
        except Exception as e:
            raise PreemptionError(
                preempted_job.job_id,
                preempting_job.job_id,
                f"Failed to terminate K8s job: {e}",
            )

        # Calculate priority boost
        original_priority = preempted_job.priority
        new_priority = self._calculate_priority_boost(preempted_job)
        priority_boost_applied = new_priority != original_priority

        # Create preemption event
        event = PreemptionEvent(
            event_id=event_id,
            preempted_job_id=preempted_job.job_id,
            preempting_job_id=preempting_job.job_id,
            organization_id=preempted_job.organization_id,
            reason=reason,
            checkpoint_saved=checkpoint_saved,
            checkpoint_s3_path=checkpoint_s3_path,
            preempted_at=now,
            re_queued=True,  # Will be set by caller after re-queue
            priority_boost_applied=priority_boost_applied,
            original_priority=original_priority,
            new_priority=new_priority,
        )

        logger.info(
            "Job preemption completed",
            extra={
                "event_id": event_id,
                "checkpoint_saved": checkpoint_saved,
                "priority_boost_applied": priority_boost_applied,
            },
        )

        return event

    async def handle_spot_interruption(
        self,
        job: GPUJob,
    ) -> PreemptionEvent:
        """Handle AWS Spot instance interruption.

        Called when we receive a Spot interruption warning from the
        Node Termination Handler. We have 2 minutes to save state.

        Args:
            job: The job running on the interrupted node.

        Returns:
            PreemptionEvent with details.
        """
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        logger.warning(
            "Handling Spot interruption",
            extra={
                "event_id": event_id,
                "job_id": job.job_id,
                "organization_id": job.organization_id,
            },
        )

        checkpoint_saved = False
        checkpoint_s3_path = None

        # Try to save checkpoint with reduced timeout (Spot gives ~2 min warning)
        if job.checkpoint_enabled:
            try:
                checkpoint_saved = await self._signal_and_wait_checkpoint(
                    job,
                    timeout_seconds=90,  # 90 seconds for Spot interruption
                )
                if checkpoint_saved:
                    checkpoint_s3_path = job.checkpoint_s3_path
            except (CheckpointError, asyncio.TimeoutError) as e:
                logger.warning(f"Spot checkpoint failed for job {job.job_id}: {e}")

        # Create preemption event
        event = PreemptionEvent(
            event_id=event_id,
            preempted_job_id=job.job_id,
            preempting_job_id="spot_interruption",  # No preempting job
            organization_id=job.organization_id,
            reason=PreemptionReason.SPOT_INTERRUPTION,
            checkpoint_saved=checkpoint_saved,
            checkpoint_s3_path=checkpoint_s3_path,
            preempted_at=now,
            re_queued=True,
            priority_boost_applied=True,  # Always boost Spot-interrupted jobs
            original_priority=job.priority,
            new_priority=GPUJobPriority.HIGH,  # Boost to HIGH for Spot
        )

        return event

    def _can_preempt(
        self,
        preempting_priority: GPUJobPriority,
        preempted_priority: GPUJobPriority,
    ) -> bool:
        """Check if preemption is allowed based on priorities.

        Per ADR-061:
        - HIGH can preempt LOW
        - Nothing can preempt NORMAL or HIGH

        Args:
            preempting_priority: Priority of job wanting to run.
            preempted_priority: Priority of running job.

        Returns:
            True if preemption is allowed.
        """
        # Only HIGH priority can preempt
        if preempting_priority != GPUJobPriority.HIGH:
            return False

        # Only LOW priority can be preempted
        if preempted_priority != GPUJobPriority.LOW:
            return False

        return True

    def _calculate_priority_boost(self, job: GPUJob) -> GPUJobPriority:
        """Calculate new priority for re-queued preempted job.

        Per ADR-061:
        - LOW -> NORMAL (promotion to prevent starvation)
        - NORMAL -> NORMAL (already protected)

        Args:
            job: The preempted job.

        Returns:
            New priority level.
        """
        if not self.priority_boost:
            return job.priority

        if job.priority == GPUJobPriority.LOW:
            return GPUJobPriority.NORMAL

        return job.priority

    async def _signal_and_wait_checkpoint(
        self,
        job: GPUJob,
        timeout_seconds: int | None = None,
    ) -> bool:
        """Signal job to checkpoint and wait for completion.

        Args:
            job: Job to checkpoint.
            timeout_seconds: Custom timeout (uses default if None).

        Returns:
            True if checkpoint was saved successfully.
        """
        timeout = timeout_seconds or self.checkpoint_timeout

        # Signal checkpoint via K8s client
        if self.k8s_client:
            await self.k8s_client.signal_checkpoint(job.job_id)

        # Wait for checkpoint marker in S3
        try:
            result = await asyncio.wait_for(
                self._poll_checkpoint_marker(job),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Checkpoint timeout for job {job.job_id} after {timeout}s")
            return False

    async def _poll_checkpoint_marker(
        self,
        job: GPUJob,
        poll_interval: float = 5.0,
    ) -> bool:
        """Poll for checkpoint marker in S3.

        Args:
            job: Job to check checkpoint for.
            poll_interval: Seconds between polls.

        Returns:
            True when checkpoint marker is found.
        """
        if not job.checkpoint_s3_path:
            return False

        while True:
            if self.k8s_client:
                marker_exists = await self.k8s_client.check_checkpoint_marker(job)
                if marker_exists:
                    return True

            await asyncio.sleep(poll_interval)

    async def _terminate_k8s_job(self, job: GPUJob) -> None:
        """Terminate the Kubernetes job.

        Args:
            job: Job to terminate.
        """
        if self.k8s_client:
            await self.k8s_client.delete_job(job.job_id)

        logger.info(
            "Terminated K8s job for preemption",
            extra={"job_id": job.job_id},
        )


# Singleton instance
_preemption_manager: PreemptionManager | None = None


def get_preemption_manager() -> PreemptionManager:
    """Get or create the preemption manager singleton."""
    global _preemption_manager
    if _preemption_manager is None:
        _preemption_manager = PreemptionManager()
    return _preemption_manager


def init_preemption_manager(
    k8s_client: GPUJobK8sClient,
    s3_client=None,
) -> PreemptionManager:
    """Initialize the preemption manager with dependencies.

    Args:
        k8s_client: Kubernetes client for job management.
        s3_client: S3 client for checkpoint verification.

    Returns:
        Initialized PreemptionManager.
    """
    global _preemption_manager
    _preemption_manager = PreemptionManager(
        k8s_client=k8s_client,
        s3_client=s3_client,
    )
    return _preemption_manager
