"""
Agent Orchestrator HTTP Server with SQS Queue Consumer.

This module provides an HTTP server wrapper around the System2Orchestrator,
enabling warm pool deployment with Kubernetes health probes and SQS-based
job consumption.

Architecture (Hybrid Architecture Pattern):
    1. HTTP Server provides /health endpoints for K8s probes
    2. Background task polls SQS for jobs
    3. System2Orchestrator processes jobs
    4. Results stored in DynamoDB
    5. Optional webhook callback on completion

Usage:
    # As HTTP server (warm pool mode):
    python -m src.agents.orchestrator_server

    # With environment variables:
    ENVIRONMENT=dev SQS_QUEUE_URL=... python -m src.agents.orchestrator_server
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, cast

import boto3
import httpx
import uvicorn
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add src to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.agents.agent_orchestrator import (
    System2Orchestrator,
    create_system2_orchestrator,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================


class Config:
    """Server configuration from environment variables."""

    ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
    PROJECT_NAME = os.getenv("PROJECT_NAME", "aura")
    PORT = int(os.getenv("PORT", "8080"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    HOST = os.getenv(
        "HOST", "0.0.0.0"
    )  # nosec B104 - intentional for container binding

    # Orchestrator Configuration (check early for mock mode)
    USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "false").lower() == "true"
    ENABLE_MCP = os.getenv("ENABLE_MCP", "false").lower() == "true"
    ENABLE_TITAN_MEMORY = os.getenv("ENABLE_TITAN_MEMORY", "false").lower() == "true"

    # AWS Configuration - Region is required (no hardcoded defaults)
    AWS_REGION = os.getenv("AWS_REGION")
    if not AWS_REGION:
        if USE_MOCK_LLM:
            # Allow fallback for local mock development only
            AWS_REGION = "us-east-1"
        else:
            raise ValueError(
                "AWS_REGION environment variable is required. "
                "Set AWS_REGION via ConfigMap or use USE_MOCK_LLM=true for local development."
            )

    # SQS Configuration - Queue URL is required (no hardcoded account IDs)
    SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
    if not SQS_QUEUE_URL:
        _aws_account_id = os.getenv("AWS_ACCOUNT_ID")
        if not _aws_account_id:
            raise ValueError(
                "SQS_QUEUE_URL or AWS_ACCOUNT_ID environment variable is required. "
                "These should be set via Kubernetes ConfigMap."
            )
        SQS_QUEUE_URL = (
            f"https://sqs.{AWS_REGION}.amazonaws.com/"
            f"{_aws_account_id}/"
            f"{PROJECT_NAME}-orchestrator-tasks-{ENVIRONMENT}"
        )

    SQS_POLL_INTERVAL = int(os.getenv("SQS_POLL_INTERVAL", "5"))  # seconds
    SQS_VISIBILITY_TIMEOUT = int(
        os.getenv("SQS_VISIBILITY_TIMEOUT", "1800")
    )  # 30 minutes
    SQS_MAX_MESSAGES = int(os.getenv("SQS_MAX_MESSAGES", "1"))  # Process one at a time
    SQS_LONG_POLL_WAIT = int(os.getenv("SQS_LONG_POLL_WAIT", "10"))  # seconds

    # DynamoDB Configuration - Table name derived from project/env
    DYNAMODB_TABLE = os.getenv(
        "DYNAMODB_TABLE",
        f"{PROJECT_NAME}-orchestrator-jobs-{ENVIRONMENT}",
    )

    # Webhook callback configuration
    CALLBACK_TIMEOUT = int(os.getenv("CALLBACK_TIMEOUT", "30"))  # seconds


# =============================================================================
# Pydantic Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "1.0.0"
    environment: str
    uptime_seconds: float
    jobs_processed: int = 0
    jobs_failed: int = 0
    queue_consumer_active: bool = False


class JobStatusResponse(BaseModel):
    """Current job processing status."""

    processing: bool
    current_job_id: str | None = None
    started_at: str | None = None
    jobs_in_queue: int = 0


# =============================================================================
# Queue Consumer
# =============================================================================


class QueueConsumer:
    """
    SQS Queue Consumer for orchestrator jobs.

    Polls SQS for new jobs and processes them using System2Orchestrator.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.sqs = boto3.client("sqs", region_name=config.AWS_REGION)
        self.dynamodb = boto3.resource("dynamodb", region_name=config.AWS_REGION)
        self.table = self.dynamodb.Table(config.DYNAMODB_TABLE)

        self._running = False
        self._current_job_id: str | None = None
        self._current_job_started: str | None = None
        self._jobs_processed = 0
        self._jobs_failed = 0
        self._orchestrator: System2Orchestrator | None = None

    @property
    def is_processing(self) -> bool:
        """Check if currently processing a job."""
        return self._current_job_id is not None

    @property
    def stats(self) -> dict[str, Any]:
        """Get consumer statistics."""
        return {
            "running": self._running,
            "processing": self.is_processing,
            "current_job_id": self._current_job_id,
            "current_job_started": self._current_job_started,
            "jobs_processed": self._jobs_processed,
            "jobs_failed": self._jobs_failed,
        }

    async def start(self):
        """Start the queue consumer."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting queue consumer for {self.config.SQS_QUEUE_URL}")

        # Initialize orchestrator
        try:
            self._orchestrator = create_system2_orchestrator(
                use_mock=self.config.USE_MOCK_LLM,
                enable_mcp=self.config.ENABLE_MCP,
                enable_titan_memory=self.config.ENABLE_TITAN_MEMORY,
            )
            logger.info("System2Orchestrator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            self._running = False
            raise

        # Start polling loop
        asyncio.create_task(self._poll_loop())

    async def stop(self):
        """Stop the queue consumer."""
        self._running = False
        logger.info("Queue consumer stopped")

    async def _poll_loop(self):
        """Main polling loop for SQS messages."""
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
                await asyncio.sleep(self.config.SQS_POLL_INTERVAL)

            # Wait before next poll
            await asyncio.sleep(self.config.SQS_POLL_INTERVAL)

    async def _poll_once(self):
        """Poll SQS once for messages."""
        try:
            response = self.sqs.receive_message(
                QueueUrl=cast(str, self.config.SQS_QUEUE_URL),
                MaxNumberOfMessages=self.config.SQS_MAX_MESSAGES,
                WaitTimeSeconds=self.config.SQS_LONG_POLL_WAIT,
                VisibilityTimeout=self.config.SQS_VISIBILITY_TIMEOUT,
                MessageAttributeNames=["All"],
            )
        except ClientError as e:
            logger.error(f"Failed to receive SQS messages: {e}")
            return

        messages = response.get("Messages", [])
        if not messages:
            return

        for message in messages:
            await self._process_message(cast(dict[str, Any], message))

    async def _process_message(self, message: dict[str, Any]):
        """Process a single SQS message."""
        receipt_handle = message["ReceiptHandle"]
        body = json.loads(message["Body"])

        job_id = body.get("job_id", "unknown")
        task_id = body.get("task_id", "unknown")
        prompt = body.get("prompt", "")
        callback_url = body.get("callback_url")

        self._current_job_id = job_id
        self._current_job_started = datetime.now(timezone.utc).isoformat()

        logger.info(f"Processing job {job_id} (task {task_id})")

        try:
            # Update status to RUNNING
            await self._update_job_status(job_id, "RUNNING")

            # Execute orchestrator
            result = await self._execute_orchestrator(prompt, job_id)

            # Update status to SUCCEEDED with result
            await self._update_job_status(
                job_id,
                "SUCCEEDED",
                result=result,
            )

            # Send webhook callback if configured
            if callback_url:
                await self._send_callback(callback_url, job_id, "SUCCEEDED", result)

            # Delete message from queue
            self.sqs.delete_message(
                QueueUrl=cast(str, self.config.SQS_QUEUE_URL),
                ReceiptHandle=receipt_handle,
            )

            self._jobs_processed += 1
            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")

            # Update status to FAILED
            await self._update_job_status(
                job_id,
                "FAILED",
                error_message=str(e),
            )

            # Send webhook callback if configured
            if callback_url:
                await self._send_callback(
                    callback_url, job_id, "FAILED", {"error": str(e)}
                )

            # Delete message (don't retry - job state is in DynamoDB)
            self.sqs.delete_message(
                QueueUrl=cast(str, self.config.SQS_QUEUE_URL),
                ReceiptHandle=receipt_handle,
            )

            self._jobs_failed += 1

        finally:
            self._current_job_id = None
            self._current_job_started = None

    async def _execute_orchestrator(self, prompt: str, job_id: str) -> dict[str, Any]:
        """Execute the orchestrator for a job."""
        if not self._orchestrator:
            raise RuntimeError("Orchestrator not initialized")

        # Execute the orchestrator
        result = await self._orchestrator.execute_request(prompt)

        return {
            "status": result.get("status", "UNKNOWN"),
            "handover": result.get("handover", ""),
            "metrics": result.get("metrics", {}),
            "job_id": job_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _update_job_status(
        self,
        job_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ):
        """Update job status in DynamoDB."""
        now = datetime.now(timezone.utc).isoformat()

        update_expr = "SET #status = :status, updated_at = :updated"
        expr_names = {"#status": "status"}
        expr_values: dict[str, Any] = {":status": status, ":updated": now}

        if status == "RUNNING":
            update_expr += ", started_at = if_not_exists(started_at, :started)"
            expr_values[":started"] = now

        if result:
            update_expr += ", #result = :result"
            expr_names["#result"] = "result"
            expr_values[":result"] = result

        if error_message:
            update_expr += ", error_message = :error"
            expr_values[":error"] = error_message

        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            update_expr += ", completed_at = :completed"
            expr_values[":completed"] = now

        try:
            self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
        except ClientError as e:
            logger.error(f"Failed to update job status: {e}")
            raise

    async def _send_callback(
        self,
        callback_url: str,
        job_id: str,
        status: str,
        data: dict[str, Any],
    ):
        """Send webhook callback."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    callback_url,
                    json={
                        "job_id": job_id,
                        "status": status,
                        "data": data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    timeout=float(self.config.CALLBACK_TIMEOUT),
                )
                response.raise_for_status()
                logger.info(f"Callback sent to {callback_url} for job {job_id}")
        except Exception as e:
            logger.error(f"Failed to send callback: {e}")

    async def get_queue_depth(self) -> int:
        """Get approximate number of messages in queue."""
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=cast(str, self.config.SQS_QUEUE_URL),
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            return int(response["Attributes"].get("ApproximateNumberOfMessages", 0))
        except ClientError:
            return -1


# =============================================================================
# FastAPI Application
# =============================================================================

# Global state
config = Config()
queue_consumer: QueueConsumer | None = None
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global queue_consumer

    # Startup
    logger.info(f"Starting Agent Orchestrator Server (env={config.ENVIRONMENT})")

    queue_consumer = QueueConsumer(config)
    await queue_consumer.start()

    yield

    # Shutdown
    if queue_consumer:
        await queue_consumer.stop()
    logger.info("Agent Orchestrator Server shutdown complete")


app = FastAPI(
    title="Agent Orchestrator Server",
    description="HTTP server with SQS queue consumer for agent orchestration jobs",
    version="1.0.0",
    lifespan=lifespan,
)


# =============================================================================
# Health Endpoints
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
@app.get("/health/live", response_model=HealthResponse, tags=["Health"])
async def health_live():
    """
    Liveness probe - indicates the server is running.

    Kubernetes uses this to know if the container should be restarted.
    """
    return HealthResponse(
        status="healthy",
        environment=config.ENVIRONMENT,
        uptime_seconds=time.time() - start_time,
        jobs_processed=queue_consumer._jobs_processed if queue_consumer else 0,
        jobs_failed=queue_consumer._jobs_failed if queue_consumer else 0,
        queue_consumer_active=queue_consumer._running if queue_consumer else False,
    )


@app.get("/health/ready", response_model=HealthResponse, tags=["Health"])
async def health_ready():
    """
    Readiness probe - indicates the server is ready to process jobs.

    Kubernetes uses this to know if the pod should receive traffic.
    """
    if not queue_consumer or not queue_consumer._running:
        raise HTTPException(status_code=503, detail="Queue consumer not running")

    return HealthResponse(
        status="ready",
        environment=config.ENVIRONMENT,
        uptime_seconds=time.time() - start_time,
        jobs_processed=queue_consumer._jobs_processed,
        jobs_failed=queue_consumer._jobs_failed,
        queue_consumer_active=True,
    )


@app.get("/health/startup", response_model=HealthResponse, tags=["Health"])
async def health_startup():
    """
    Startup probe - indicates the server has started.

    Kubernetes uses this to know when the container has started successfully.
    """
    return HealthResponse(
        status="started",
        environment=config.ENVIRONMENT,
        uptime_seconds=time.time() - start_time,
        queue_consumer_active=queue_consumer._running if queue_consumer else False,
    )


# =============================================================================
# Status Endpoints
# =============================================================================


@app.get("/status", response_model=JobStatusResponse, tags=["Status"])
async def get_status():
    """Get current processing status."""
    if not queue_consumer:
        raise HTTPException(status_code=503, detail="Queue consumer not initialized")

    queue_depth = await queue_consumer.get_queue_depth()

    return JobStatusResponse(
        processing=queue_consumer.is_processing,
        current_job_id=queue_consumer._current_job_id,
        started_at=queue_consumer._current_job_started,
        jobs_in_queue=queue_depth,
    )


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """Get Prometheus-compatible metrics."""
    if not queue_consumer:
        return ""

    stats = queue_consumer.stats
    uptime = time.time() - start_time

    metrics = f"""# HELP orchestrator_jobs_processed_total Total jobs processed
# TYPE orchestrator_jobs_processed_total counter
orchestrator_jobs_processed_total {stats['jobs_processed']}

# HELP orchestrator_jobs_failed_total Total jobs failed
# TYPE orchestrator_jobs_failed_total counter
orchestrator_jobs_failed_total {stats['jobs_failed']}

# HELP orchestrator_uptime_seconds Server uptime in seconds
# TYPE orchestrator_uptime_seconds gauge
orchestrator_uptime_seconds {uptime}

# HELP orchestrator_processing Is currently processing a job
# TYPE orchestrator_processing gauge
orchestrator_processing {1 if stats['processing'] else 0}

# HELP orchestrator_queue_consumer_running Is queue consumer running
# TYPE orchestrator_queue_consumer_running gauge
orchestrator_queue_consumer_running {1 if stats['running'] else 0}
"""
    return metrics


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Main entry point."""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start server
    logger.info(f"Starting server on port {config.PORT}")
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
