"""Queue dispatcher for GPU job scheduling.

Worker that polls SQS FIFO queue and dispatches jobs per ADR-061 Phase 2.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.services.gpu_scheduler.exceptions import PreemptionError, QueueDispatchError
from src.services.gpu_scheduler.models import (
    GPUJob,
    GPUJobPriority,
    GPUJobStatus,
    QueuedJob,
)

if TYPE_CHECKING:
    from src.services.gpu_scheduler.gpu_scheduler_service import GPUSchedulerService
    from src.services.gpu_scheduler.k8s_client import GPUJobK8sClient
    from src.services.gpu_scheduler.preemption_manager import PreemptionManager
    from src.services.gpu_scheduler.queue_engine import GPUQueueEngine

logger = logging.getLogger(__name__)

# Dispatcher configuration
POLL_INTERVAL_SECONDS = 5
STARVATION_CHECK_INTERVAL_SECONDS = 60
MAX_BATCH_SIZE = 10
SQS_WAIT_TIME_SECONDS = 20  # Long polling


class GPUQueueDispatcher:
    """Worker that polls the GPU job queue and dispatches jobs.

    Responsibilities:
    1. Poll SQS FIFO queue for new jobs
    2. Add jobs to priority queue engine
    3. Dispatch jobs respecting priority and fairness
    4. Handle preemption when needed
    5. Promote starved jobs periodically
    6. Update job status in DynamoDB

    Can run as:
    - Async loop in the API service
    - Standalone Lambda function
    - Kubernetes Deployment
    """

    def __init__(
        self,
        scheduler_service: GPUSchedulerService | None = None,
        queue_engine: GPUQueueEngine | None = None,
        preemption_manager: PreemptionManager | None = None,
        k8s_client: GPUJobK8sClient | None = None,
        sqs_client: Any | None = None,
        queue_url: str | None = None,
        poll_interval: int = POLL_INTERVAL_SECONDS,
        starvation_check_interval: int = STARVATION_CHECK_INTERVAL_SECONDS,
    ):
        """Initialize the dispatcher.

        Args:
            scheduler_service: GPU scheduler service for job operations.
            queue_engine: Queue engine for priority scheduling.
            preemption_manager: Manager for job preemption.
            k8s_client: Kubernetes client for job management.
            sqs_client: SQS client for queue operations.
            queue_url: SQS queue URL.
            poll_interval: Seconds between poll cycles.
            starvation_check_interval: Seconds between starvation checks.
        """
        self.service = scheduler_service
        self.queue_engine = queue_engine
        self.preemption_manager = preemption_manager
        self.k8s_client = k8s_client
        self.sqs_client = sqs_client
        self.queue_url = queue_url

        self.poll_interval = poll_interval
        self.starvation_check_interval = starvation_check_interval

        self._running = False
        self._last_starvation_check = datetime.now(timezone.utc)
        self._dispatch_count = 0
        self._error_count = 0

    async def start(self) -> None:
        """Start the dispatcher loop."""
        self._running = True
        logger.info("GPU Queue Dispatcher started")

        while self._running:
            try:
                await self._poll_and_dispatch()
                await self._check_starvation()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Dispatcher cancelled")
                break
            except Exception as e:
                self._error_count += 1
                logger.error(f"Dispatcher error: {e}", exc_info=True)
                # Back off on errors
                await asyncio.sleep(self.poll_interval * 2)

    async def stop(self) -> None:
        """Stop the dispatcher loop gracefully."""
        self._running = False
        logger.info(
            "GPU Queue Dispatcher stopping",
            extra={
                "dispatch_count": self._dispatch_count,
                "error_count": self._error_count,
            },
        )

    async def _poll_and_dispatch(self) -> None:
        """Poll SQS and dispatch jobs from priority queue."""
        # 1. Poll SQS for new job messages
        messages = await self._poll_sqs()

        # 2. Add new jobs to priority queue
        for msg in messages:
            try:
                await self._process_sqs_message(msg)
            except Exception as e:
                logger.error(f"Failed to process SQS message: {e}")
                # Don't delete message so it can be retried

        # 3. Try to dispatch jobs from priority queue
        await self._dispatch_ready_jobs()

    async def _process_sqs_message(self, message: dict) -> None:
        """Process a single SQS message.

        Args:
            message: SQS message dict.
        """
        body = json.loads(message.get("Body", "{}"))
        job_id = body.get("job_id")
        organization_id = body.get("organization_id")

        if not job_id or not organization_id:
            logger.warning(f"Invalid SQS message, missing job_id or org_id: {body}")
            await self._delete_sqs_message(message["ReceiptHandle"])
            return

        # Fetch full job from DynamoDB
        if self.service:
            job = await self.service.get_job(organization_id, job_id)
            if job and job.status == GPUJobStatus.QUEUED:
                if self.queue_engine:
                    self.queue_engine.enqueue(job)
                logger.debug(f"Enqueued job {job_id} from SQS")

        # Delete the SQS message
        await self._delete_sqs_message(message["ReceiptHandle"])

    async def _dispatch_ready_jobs(self) -> None:
        """Dispatch jobs that are ready to run."""
        if not self.queue_engine:
            return

        while True:
            queued_job = self.queue_engine.dequeue()
            if not queued_job:
                break

            # Check if preemption is needed for HIGH priority
            if not self.queue_engine.can_start_job(queued_job.priority):
                if queued_job.priority == GPUJobPriority.HIGH:
                    await self._handle_preemption(queued_job)
                else:
                    # Re-queue the job
                    if self.service:
                        job = await self.service.get_job(
                            queued_job.organization_id,
                            queued_job.job_id,
                        )
                        if job:
                            self.queue_engine.enqueue(job)
                    break

            # Start the job
            await self._start_job(queued_job)

    async def _start_job(self, queued_job: QueuedJob) -> None:
        """Start a GPU job on Kubernetes.

        Args:
            queued_job: Job to start.
        """
        if not self.service or not self.k8s_client:
            logger.warning("Cannot start job: service or k8s_client not configured")
            return

        try:
            # Get full job from DynamoDB
            job = await self.service.get_job(
                queued_job.organization_id,
                queued_job.job_id,
            )

            if not job:
                logger.warning(f"Job {queued_job.job_id} not found in DynamoDB")
                return

            # Create K8s job
            k8s_job_name = await self.k8s_client.create_job(job)

            # Update status in DynamoDB
            await self.service.update_job_status(
                organization_id=job.organization_id,
                job_id=job.job_id,
                status=GPUJobStatus.STARTING,
                kubernetes_job_name=k8s_job_name,
            )

            # Mark as running in queue engine
            self.queue_engine.mark_job_running(
                job.job_id,
                job.priority,
                job.organization_id,
            )

            self._dispatch_count += 1

            logger.info(
                "Started GPU job",
                extra={
                    "job_id": job.job_id,
                    "priority": job.priority.value,
                    "k8s_job": k8s_job_name,
                },
            )

        except Exception as e:
            logger.error(f"Failed to start job {queued_job.job_id}: {e}")
            raise QueueDispatchError(queued_job.job_id, str(e))

    async def _handle_preemption(self, high_priority_job: QueuedJob) -> None:
        """Handle preemption for a high-priority job.

        Args:
            high_priority_job: HIGH priority job that needs to run.
        """
        if not self.queue_engine or not self.preemption_manager or not self.service:
            return

        candidate_id = self.queue_engine.find_preemption_candidate(
            high_priority_job.priority
        )

        if not candidate_id:
            logger.warning(
                f"No preemption candidate for job {high_priority_job.job_id}"
            )
            # Re-queue the high priority job
            job = await self.service.get_job(
                high_priority_job.organization_id,
                high_priority_job.job_id,
            )
            if job:
                self.queue_engine.enqueue(job)
            return

        try:
            # Get both jobs
            high_job = await self.service.get_job(
                high_priority_job.organization_id,
                high_priority_job.job_id,
            )

            preempted_job = await self._find_running_job(candidate_id)

            if not high_job or not preempted_job:
                logger.error("Could not find jobs for preemption")
                return

            # Perform preemption
            event = await self.preemption_manager.preempt_job(
                preempting_job=high_job,
                preempted_job=preempted_job,
            )

            # Mark preempted job as cancelled in queue engine
            self.queue_engine.mark_job_completed(
                preempted_job.job_id,
                preempted_job.priority,
                preempted_job.organization_id,
            )

            # Record preemption for metrics
            self.queue_engine.record_preemption()

            # Re-queue preempted job with boosted priority
            if event.re_queued:
                preempted_job.priority = event.new_priority or preempted_job.priority
                preempted_job.status = GPUJobStatus.QUEUED
                self.queue_engine.enqueue(preempted_job)

                # Update in DynamoDB
                await self.service.update_job_status(
                    organization_id=preempted_job.organization_id,
                    job_id=preempted_job.job_id,
                    status=GPUJobStatus.QUEUED,
                )

            # Now start the high priority job
            await self._start_job(high_priority_job)

            logger.info(
                "Preemption completed",
                extra={
                    "preempted_job_id": preempted_job.job_id,
                    "preempting_job_id": high_job.job_id,
                    "checkpoint_saved": event.checkpoint_saved,
                },
            )

        except PreemptionError as e:
            logger.error(f"Preemption failed: {e}")
            # Re-queue the high priority job
            job = await self.service.get_job(
                high_priority_job.organization_id,
                high_priority_job.job_id,
            )
            if job:
                self.queue_engine.enqueue(job)

    async def _check_starvation(self) -> None:
        """Periodically check for and promote starved jobs."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_starvation_check).total_seconds()

        if elapsed < self.starvation_check_interval:
            return

        if self.queue_engine:
            promoted = self.queue_engine.promote_starved_jobs()
            if promoted:
                logger.info(f"Promoted {len(promoted)} starved jobs")

        self._last_starvation_check = now

    async def _poll_sqs(self) -> list[dict]:
        """Poll SQS for new job messages.

        Returns:
            List of SQS message dicts.
        """
        if not self.sqs_client or not self.queue_url:
            return []

        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=MAX_BATCH_SIZE,
                WaitTimeSeconds=SQS_WAIT_TIME_SECONDS,
                MessageAttributeNames=["All"],
            )

            return response.get("Messages", [])

        except Exception as e:
            logger.error(f"Failed to poll SQS: {e}")
            return []

    async def _delete_sqs_message(self, receipt_handle: str) -> None:
        """Delete a processed SQS message.

        Args:
            receipt_handle: SQS message receipt handle.
        """
        if not self.sqs_client or not self.queue_url:
            return

        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )
        except Exception as e:
            logger.error(f"Failed to delete SQS message: {e}")

    async def _find_running_job(self, job_id: str) -> GPUJob | None:
        """Find a running job by ID.

        Uses reverse lookup to find the org_id for a running job.

        Args:
            job_id: Job ID to find.

        Returns:
            GPUJob if found, None otherwise.
        """
        if not self.service or not self.queue_engine:
            return None

        # Single pass: find org_id for the job_id
        for org_id, org_jobs in self.queue_engine._running_by_org.items():
            if job_id in org_jobs:
                return await self.service.get_job(org_id, job_id)

        return None

    def get_stats(self) -> dict:
        """Get dispatcher statistics.

        Returns:
            Dict with dispatcher stats.
        """
        return {
            "running": self._running,
            "dispatch_count": self._dispatch_count,
            "error_count": self._error_count,
            "queue_size": self.queue_engine.size() if self.queue_engine else 0,
        }


# Singleton instance
_dispatcher: GPUQueueDispatcher | None = None


def get_queue_dispatcher() -> GPUQueueDispatcher:
    """Get or create the queue dispatcher singleton."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = GPUQueueDispatcher()
    return _dispatcher


def init_queue_dispatcher(
    scheduler_service: GPUSchedulerService,
    queue_engine: GPUQueueEngine,
    preemption_manager: PreemptionManager,
    k8s_client: GPUJobK8sClient,
    sqs_client: Any,
    queue_url: str,
) -> GPUQueueDispatcher:
    """Initialize the queue dispatcher with dependencies.

    Args:
        scheduler_service: GPU scheduler service.
        queue_engine: Queue engine.
        preemption_manager: Preemption manager.
        k8s_client: Kubernetes client.
        sqs_client: SQS client.
        queue_url: SQS queue URL.

    Returns:
        Initialized GPUQueueDispatcher.
    """
    global _dispatcher
    _dispatcher = GPUQueueDispatcher(
        scheduler_service=scheduler_service,
        queue_engine=queue_engine,
        preemption_manager=preemption_manager,
        k8s_client=k8s_client,
        sqs_client=sqs_client,
        queue_url=queue_url,
    )
    return _dispatcher
