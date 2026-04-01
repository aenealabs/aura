"""Stalled job detection and alerting service.

Monitors running GPU jobs for progress and detects stalled workloads
that may need intervention (restart, cancel, or manual review).

Detection thresholds (per ADR-061):
- WARNING: No progress for 5+ minutes
- STALLED: No progress for 15+ minutes
- CRITICAL: No progress for 30+ minutes
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.services.gpu_scheduler.exceptions import GPUSchedulerError
from src.services.gpu_scheduler.models import (
    GPUJob,
    GPUJobStatus,
    GPUJobType,
    StalledJobInfo,
    StalledJobStatus,
)

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table
    from mypy_boto3_sns.client import SNSClient

logger = logging.getLogger(__name__)


# Stall detection thresholds in minutes
THRESHOLD_WARNING_MINUTES = 5
THRESHOLD_STALLED_MINUTES = 15
THRESHOLD_CRITICAL_MINUTES = 30

# Expected job durations by type (for overdue detection)
EXPECTED_DURATION_BY_TYPE: dict[GPUJobType, int] = {
    GPUJobType.EMBEDDING_GENERATION: 30,
    GPUJobType.LOCAL_INFERENCE: 15,
    GPUJobType.VULNERABILITY_TRAINING: 120,
    GPUJobType.SWE_RL_TRAINING: 240,
    GPUJobType.MEMORY_CONSOLIDATION: 60,
}


class StalledJobDetector:
    """Detects and alerts on stalled GPU jobs.

    Monitors running jobs for progress updates and classifies them
    based on time since last progress report.

    Attributes:
        jobs_table: DynamoDB table for job data.
        sns_client: SNS client for sending alerts.
        alert_topic_arn: SNS topic ARN for alerts.
        check_interval_seconds: How often to run detection loop.
    """

    def __init__(
        self,
        jobs_table: "Table",
        sns_client: "SNSClient | None" = None,
        alert_topic_arn: str | None = None,
        check_interval_seconds: int = 60,
    ):
        """Initialize the stalled job detector.

        Args:
            jobs_table: DynamoDB table for job data.
            sns_client: SNS client for sending alerts.
            alert_topic_arn: SNS topic ARN for alerts.
            check_interval_seconds: How often to run detection (default: 60s).
        """
        self.jobs_table = jobs_table
        self.sns_client = sns_client
        self.alert_topic_arn = alert_topic_arn
        self.check_interval_seconds = check_interval_seconds

        # Track which jobs have been alerted to avoid duplicate alerts
        self._alerted_jobs: dict[str, datetime] = {}

        # Background task handle
        self._detection_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background detection loop."""
        if self._running:
            logger.warning("Stalled job detector already running")
            return

        self._running = True
        self._detection_task = asyncio.create_task(self._detection_loop())
        logger.info("Started stalled job detector")

    async def stop(self) -> None:
        """Stop the background detection loop."""
        self._running = False
        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
            self._detection_task = None
        logger.info("Stopped stalled job detector")

    async def _detection_loop(self) -> None:
        """Background loop that periodically checks for stalled jobs."""
        while self._running:
            try:
                await self.detect_and_alert()
            except Exception as e:
                logger.error(f"Error in stalled job detection loop: {e}")

            await asyncio.sleep(self.check_interval_seconds)

    async def detect_and_alert(self) -> list[StalledJobInfo]:
        """Detect stalled jobs and send alerts.

        Returns:
            List of stalled job info for jobs that were alerted.
        """
        running_jobs = await self._get_running_jobs()
        stalled_jobs = []

        for job in running_jobs:
            stall_info = self._analyze_job_progress(job)

            # Only alert for WARNING, STALLED, or CRITICAL
            if stall_info.status != StalledJobStatus.HEALTHY:
                # Check if we already alerted for this job recently
                if not self._should_alert(job.job_id, stall_info.status):
                    continue

                # Send alert
                await self._send_alert(stall_info)
                stalled_jobs.append(stall_info)

                # Mark job as alerted
                self._alerted_jobs[job.job_id] = datetime.now(timezone.utc)

        # Cleanup old alert tracking entries
        self._cleanup_alert_tracking()

        return stalled_jobs

    async def check_single_job(self, job: GPUJob) -> StalledJobInfo:
        """Check a single job for stall status.

        Args:
            job: The GPU job to check.

        Returns:
            Stall information for the job.
        """
        return self._analyze_job_progress(job)

    async def get_stalled_jobs(
        self,
        organization_id: str | None = None,
        min_status: StalledJobStatus = StalledJobStatus.WARNING,
    ) -> list[StalledJobInfo]:
        """Get all jobs that are at or above a stall threshold.

        Args:
            organization_id: Optional filter by organization.
            min_status: Minimum stall status to include.

        Returns:
            List of stalled job information.
        """
        running_jobs = await self._get_running_jobs(organization_id)
        stalled_jobs = []

        status_order = {
            StalledJobStatus.HEALTHY: 0,
            StalledJobStatus.WARNING: 1,
            StalledJobStatus.STALLED: 2,
            StalledJobStatus.CRITICAL: 3,
        }
        min_order = status_order[min_status]

        for job in running_jobs:
            stall_info = self._analyze_job_progress(job)
            if status_order[stall_info.status] >= min_order:
                stalled_jobs.append(stall_info)

        return stalled_jobs

    def _analyze_job_progress(self, job: GPUJob) -> StalledJobInfo:
        """Analyze a job's progress to determine stall status.

        Args:
            job: The GPU job to analyze.

        Returns:
            Stall information for the job.
        """
        now = datetime.now(timezone.utc)

        # Calculate time since last progress
        # Use started_at if no progress has been reported yet
        last_progress_at = job.started_at
        if last_progress_at is None:
            last_progress_at = job.created_at

        # Ensure timezone-aware comparison
        if last_progress_at.tzinfo is None:
            last_progress_at = last_progress_at.replace(tzinfo=timezone.utc)

        minutes_since_progress = (now - last_progress_at).total_seconds() / 60

        # Determine stall status
        if minutes_since_progress >= THRESHOLD_CRITICAL_MINUTES:
            status = StalledJobStatus.CRITICAL
        elif minutes_since_progress >= THRESHOLD_STALLED_MINUTES:
            status = StalledJobStatus.STALLED
        elif minutes_since_progress >= THRESHOLD_WARNING_MINUTES:
            status = StalledJobStatus.WARNING
        else:
            status = StalledJobStatus.HEALTHY

        # Check if job is overdue
        expected_duration = EXPECTED_DURATION_BY_TYPE.get(job.job_type, 60)
        started_at = job.started_at or job.created_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        runtime_minutes = (now - started_at).total_seconds() / 60
        is_overdue = runtime_minutes > expected_duration * 1.5

        # Check if alert was previously sent
        alert_sent = job.job_id in self._alerted_jobs
        alert_sent_at = self._alerted_jobs.get(job.job_id)

        return StalledJobInfo(
            job_id=job.job_id,
            organization_id=job.organization_id,
            user_id=job.user_id,
            job_type=job.job_type,
            status=status,
            progress_percent=job.progress_percent or 0,
            last_progress_at=last_progress_at,
            minutes_since_progress=minutes_since_progress,
            started_at=started_at,
            expected_duration_minutes=expected_duration,
            is_overdue=is_overdue,
            alert_sent=alert_sent,
            alert_sent_at=alert_sent_at,
        )

    async def _get_running_jobs(
        self,
        organization_id: str | None = None,
    ) -> list[GPUJob]:
        """Get all currently running jobs.

        Args:
            organization_id: Optional filter by organization.

        Returns:
            List of running GPU jobs.
        """
        try:
            # Query using org_status GSI
            if organization_id:
                response = self.jobs_table.query(
                    IndexName="org-status-index",
                    KeyConditionExpression="org_status = :os",
                    ExpressionAttributeValues={
                        ":os": f"{organization_id}#{GPUJobStatus.RUNNING.value}"
                    },
                )
            else:
                # Scan for all running jobs (less efficient but needed for global check)
                response = self.jobs_table.scan(
                    FilterExpression="contains(org_status, :status)",
                    ExpressionAttributeValues={
                        ":status": f"#{GPUJobStatus.RUNNING.value}"
                    },
                )

            jobs = []
            for item in response.get("Items", []):
                try:
                    jobs.append(GPUJob.from_dynamodb_item(item))
                except Exception as e:
                    logger.warning(f"Failed to parse job item: {e}")

            return jobs

        except Exception as e:
            logger.error(f"Failed to query running jobs: {e}")
            raise GPUSchedulerError(f"Failed to get running jobs: {e}")

    def _should_alert(self, job_id: str, status: StalledJobStatus) -> bool:
        """Check if we should send an alert for a job.

        Avoids duplicate alerts by checking if we recently alerted.
        Re-alerts are sent when status escalates (e.g., WARNING -> STALLED).

        Args:
            job_id: The job ID.
            status: Current stall status.

        Returns:
            True if we should send an alert.
        """
        if job_id not in self._alerted_jobs:
            return True

        # Allow re-alert every 15 minutes for persistent issues
        last_alert = self._alerted_jobs[job_id]
        minutes_since_alert = (
            datetime.now(timezone.utc) - last_alert
        ).total_seconds() / 60

        # Re-alert for CRITICAL every 15 min, STALLED every 30 min
        if status == StalledJobStatus.CRITICAL and minutes_since_alert >= 15:
            return True
        if status == StalledJobStatus.STALLED and minutes_since_alert >= 30:
            return True

        return False

    async def _send_alert(self, stall_info: StalledJobInfo) -> None:
        """Send an SNS alert for a stalled job.

        Args:
            stall_info: Information about the stalled job.
        """
        if not self.sns_client or not self.alert_topic_arn:
            logger.warning(
                f"Alert not sent (SNS not configured): {stall_info.job_id} "
                f"is {stall_info.status.value}"
            )
            return

        try:
            severity_emoji = {
                StalledJobStatus.WARNING: "⚠️",
                StalledJobStatus.STALLED: "🔶",
                StalledJobStatus.CRITICAL: "🔴",
            }

            emoji = severity_emoji.get(stall_info.status, "ℹ️")
            subject = (
                f"{emoji} GPU Job {stall_info.status.value.upper()}: "
                f"{stall_info.job_id[:8]}"
            )

            message = f"""
GPU Job Stall Alert
==================

Job ID: {stall_info.job_id}
Organization: {stall_info.organization_id}
User: {stall_info.user_id}
Job Type: {stall_info.job_type.value}

Status: {stall_info.status.value.upper()}
Progress: {stall_info.progress_percent}%
Minutes Since Progress: {stall_info.minutes_since_progress:.1f}
Expected Duration: {stall_info.expected_duration_minutes} minutes
Is Overdue: {stall_info.is_overdue}

Started At: {stall_info.started_at.isoformat()}
Last Progress: {stall_info.last_progress_at.isoformat() if stall_info.last_progress_at else 'Never'}

Recommended Action:
- WARNING: Monitor for improvement
- STALLED: Check job logs, consider restart
- CRITICAL: Manual intervention recommended

View job: {os.environ.get("GPU_DASHBOARD_BASE_URL", "https://app.aura.local")}/gpu-jobs/{stall_info.job_id}
""".strip()

            self.sns_client.publish(
                TopicArn=self.alert_topic_arn,
                Subject=subject,
                Message=message,
                MessageAttributes={
                    "severity": {
                        "DataType": "String",
                        "StringValue": stall_info.status.value,
                    },
                    "job_id": {
                        "DataType": "String",
                        "StringValue": stall_info.job_id,
                    },
                    "organization_id": {
                        "DataType": "String",
                        "StringValue": stall_info.organization_id,
                    },
                },
            )

            logger.info(
                f"Sent stall alert for job {stall_info.job_id}: {stall_info.status.value}"
            )

        except Exception as e:
            logger.error(f"Failed to send stall alert: {e}")

    def _cleanup_alert_tracking(self) -> None:
        """Remove old entries from alert tracking to prevent memory growth."""
        now = datetime.now(timezone.utc)
        cutoff_hours = 24  # Remove entries older than 24 hours

        to_remove = []
        for job_id, alert_time in self._alerted_jobs.items():
            hours_ago = (now - alert_time).total_seconds() / 3600
            if hours_ago > cutoff_hours:
                to_remove.append(job_id)

        for job_id in to_remove:
            del self._alerted_jobs[job_id]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old alert tracking entries")


# Module-level singleton
_detector: StalledJobDetector | None = None


def get_stalled_job_detector(
    jobs_table: "Table",
    sns_client: "SNSClient | None" = None,
    alert_topic_arn: str | None = None,
) -> StalledJobDetector:
    """Get or create the stalled job detector singleton.

    Args:
        jobs_table: DynamoDB table for job data.
        sns_client: SNS client for sending alerts.
        alert_topic_arn: SNS topic ARN for alerts.

    Returns:
        The stalled job detector instance.
    """
    global _detector
    if _detector is None:
        _detector = StalledJobDetector(
            jobs_table=jobs_table,
            sns_client=sns_client,
            alert_topic_arn=alert_topic_arn,
        )
    return _detector
