"""Agent Worker - SQS Queue Consumer for Agent Tasks (Issue #19)
================================================================

Standalone worker process that runs an agent as a queue consumer.
Each worker polls tasks from its assigned SQS queue, processes them
using the appropriate agent, and sends results to the responses queue.

This enables true microservices decoupling of the agent system.

Usage:
    # Run a coder agent worker
    python -m src.agents.agent_worker --agent-type coder

    # Run with custom queue URL
    python -m src.agents.agent_worker --agent-type reviewer --queue-url $URL
"""

import argparse
import asyncio
import logging
import os
import signal
import time
from typing import TYPE_CHECKING, Any

from src.agents.base_agent import AgentTask, SQSConsumerMixin
from src.agents.messaging import AgentResultMessage, MessageType

if TYPE_CHECKING:
    from src.agents.base_agent import BaseAgent
    from src.services.agent_queue_service import AgentQueueService

logger = logging.getLogger(__name__)

# Queue URL environment variable mappings
QUEUE_URL_ENV_VARS = {
    "coder": "CODER_QUEUE_URL",
    "reviewer": "REVIEWER_QUEUE_URL",
    "validator": "VALIDATOR_QUEUE_URL",
}

# Default visibility timeouts per agent type (seconds)
VISIBILITY_TIMEOUTS = {
    "coder": 900,  # 15 minutes for code generation
    "reviewer": 600,  # 10 minutes for code review
    "validator": 600,  # 10 minutes for validation
}


class AgentWorker(SQSConsumerMixin):
    """Runs an agent as a queue consumer.

    The worker continuously polls its assigned SQS queue for tasks,
    processes them using the agent, and sends results to the
    orchestrator responses queue.

    Attributes:
        agent_type: Type of agent ("coder", "reviewer", "validator").
        agent: The agent instance that processes tasks.
        queue_service: Service for sending results to responses queue.
        running: Flag indicating if the worker is running.
        tasks_processed: Counter of successfully processed tasks.
        tasks_failed: Counter of failed tasks.
    """

    def __init__(
        self,
        agent_type: str,
        agent: "BaseAgent",
        queue_url: str | None = None,
        queue_service: "AgentQueueService | None" = None,
        visibility_timeout: int | None = None,
    ):
        """Initialize the agent worker.

        Args:
            agent_type: Type of agent ("coder", "reviewer", "validator").
            agent: The agent instance to use for task processing.
            queue_url: Optional SQS queue URL. If not provided, reads from env.
            queue_service: Optional queue service for sending results.
            visibility_timeout: Optional visibility timeout override.
        """
        self.agent_type = agent_type
        self.agent = agent
        self.running = False
        self.tasks_processed = 0
        self.tasks_failed = 0

        # Determine queue URL from parameter, env var, or default
        if queue_url:
            self._queue_url = queue_url
        else:
            env_var = QUEUE_URL_ENV_VARS.get(agent_type)
            self._queue_url = os.environ.get(env_var or "", "") if env_var else ""

        if not self._queue_url:
            logger.warning(
                f"No queue URL configured for {agent_type} worker. "
                f"Set {QUEUE_URL_ENV_VARS.get(agent_type, 'QUEUE_URL')} environment variable."
            )

        # Determine visibility timeout
        timeout = visibility_timeout or VISIBILITY_TIMEOUTS.get(agent_type, 600)

        # Initialize the SQS consumer mixin
        self.init_consumer(
            queue_url=self._queue_url,
            visibility_timeout=timeout,
            wait_time_seconds=20,
        )

        # Queue service for sending results
        self.queue_service = queue_service

        logger.info(
            f"Initialized {agent_type} worker "
            f"(queue={self._queue_url[:50]}..., visibility_timeout={timeout}s)"
        )

    async def run(
        self,
        max_tasks: int | None = None,
        shutdown_on_empty: bool = False,
    ) -> dict[str, int]:
        """Main worker loop - poll and process tasks.

        Args:
            max_tasks: Optional maximum number of tasks to process before stopping.
            shutdown_on_empty: If True, stop when queue is empty after one poll.

        Returns:
            Dict with tasks_processed and tasks_failed counts.
        """
        self.running = True
        logger.info(f"Starting {self.agent_type} worker loop")

        while self.running:
            try:
                # Poll for tasks (blocks up to wait_time_seconds)
                tasks = await self.poll_tasks(max_messages=1)

                if not tasks:
                    if shutdown_on_empty:
                        logger.info("Queue empty, shutting down")
                        break
                    continue

                # Process each task
                for task, receipt_handle in tasks:
                    await self._process_task(task, receipt_handle)

                    # Check max tasks limit
                    if max_tasks and self.tasks_processed >= max_tasks:
                        logger.info(f"Reached max tasks limit ({max_tasks})")
                        self.running = False
                        break

            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Brief pause before retry

        logger.info(
            f"Worker stopped. Processed: {self.tasks_processed}, Failed: {self.tasks_failed}"
        )

        return {
            "tasks_processed": self.tasks_processed,
            "tasks_failed": self.tasks_failed,
        }

    async def _process_task(
        self,
        task: AgentTask,
        receipt_handle: str,
    ) -> None:
        """Process a single task from the queue.

        Args:
            task: The AgentTask to process.
            receipt_handle: SQS receipt handle for message acknowledgment.
        """
        start_time = time.time()
        task_id = task.task_id
        logger.info(f"Processing task {task_id}")

        try:
            # Execute the task using the agent
            result = await self._execute_agent_task(task)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Send result to responses queue
            if self.queue_service:
                await self._send_result(
                    task=task,
                    success=True,
                    data=result,
                    error=None,
                    execution_time_ms=execution_time_ms,
                )

            # Acknowledge successful processing
            await self.ack_task(receipt_handle)
            self.tasks_processed += 1

            logger.info(
                f"Task {task_id} completed successfully "
                f"(execution_time={execution_time_ms:.1f}ms)"
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)

            # Send failure result
            if self.queue_service:
                await self._send_result(
                    task=task,
                    success=False,
                    data={},
                    error=str(e),
                    execution_time_ms=execution_time_ms,
                )

            # Make message visible again for retry (visibility timeout = 0)
            await self.nack_task(receipt_handle, visibility_timeout=0)
            self.tasks_failed += 1

    async def _execute_agent_task(self, task: AgentTask) -> dict[str, Any]:
        """Execute the task using the appropriate agent method.

        Args:
            task: The AgentTask to execute.

        Returns:
            Dict containing the agent's result.
        """
        # Import agent classes to determine which method to call
        from src.agents.coder_agent import CoderAgent
        from src.agents.reviewer_agent import ReviewerAgent
        from src.agents.validator_agent import ValidatorAgent

        if isinstance(self.agent, CoderAgent):
            # Coder generates code from context
            context = task.context  # HybridContext or dict
            result = await self.agent.generate_code(
                context=context,
                task_description=task.description,
            )
            return result

        elif isinstance(self.agent, ReviewerAgent):
            # Reviewer reviews code for security issues
            code = (
                task.context.get("code", "") if isinstance(task.context, dict) else ""
            )
            result = await self.agent.review_code(code)
            return result

        elif isinstance(self.agent, ValidatorAgent):
            # Validator validates code structure and syntax
            code = (
                task.context.get("code", "") if isinstance(task.context, dict) else ""
            )
            expected_elements = (
                task.context.get("expected_elements", [])
                if isinstance(task.context, dict)
                else []
            )
            result = await self.agent.validate_code(
                code=code,
                expected_elements=expected_elements,
            )
            return result

        else:
            raise ValueError(f"Unknown agent type: {type(self.agent)}")

    async def _send_result(
        self,
        task: AgentTask,
        success: bool,
        data: dict[str, Any],
        error: str | None,
        execution_time_ms: float,
    ) -> None:
        """Send result message to the responses queue.

        Args:
            task: The original task.
            success: Whether the task completed successfully.
            data: Result data from the agent.
            error: Error message if failed.
            execution_time_ms: Execution time in milliseconds.
        """
        if not self.queue_service:
            return

        import uuid

        result_message = AgentResultMessage(
            message_id=str(uuid.uuid4()),
            task_id=task.task_id,
            source_agent=self.agent_type,
            target_agent="orchestrator",
            message_type=MessageType.RESULT,
            payload=data,
            correlation_id=task.correlation_id or "",
            priority=task.priority,
            success=success,
            data=data,
            error=error,
            execution_time_ms=execution_time_ms,
            tokens_used=data.get("tokens_used", 0) if isinstance(data, dict) else 0,
        )

        await self.queue_service.send_result(result_message)
        logger.debug(f"Sent result for task {task.task_id} to responses queue")

    def stop(self) -> None:
        """Signal the worker to stop after completing current task."""
        logger.info(f"Stopping {self.agent_type} worker...")
        self.running = False


def create_agent_worker(
    agent_type: str,
    queue_url: str | None = None,
    llm_client: Any = None,
) -> AgentWorker:
    """Factory function to create an AgentWorker.

    Args:
        agent_type: Type of agent ("coder", "reviewer", "validator").
        queue_url: Optional SQS queue URL.
        llm_client: Optional LLM client for the agent.

    Returns:
        Configured AgentWorker instance.

    Raises:
        ValueError: If agent_type is not recognized.
    """
    from src.agents.coder_agent import CoderAgent
    from src.agents.monitoring_service import MonitorAgent
    from src.agents.reviewer_agent import ReviewerAgent
    from src.agents.validator_agent import ValidatorAgent

    monitor = MonitorAgent()

    if agent_type == "coder":
        agent = CoderAgent(llm_client=llm_client, monitor=monitor)
    elif agent_type == "reviewer":
        agent = ReviewerAgent(llm_client=llm_client, monitor=monitor)
    elif agent_type == "validator":
        agent = ValidatorAgent(llm_client=llm_client, monitor=monitor)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")

    # Create queue service for sending results
    queue_service = None
    try:
        from src.services.agent_queue_service import AgentQueueService

        queue_service = AgentQueueService()
    except Exception as e:
        logger.warning(f"Could not create queue service: {e}")

    return AgentWorker(
        agent_type=agent_type,
        agent=agent,
        queue_url=queue_url,
        queue_service=queue_service,
    )


async def main() -> None:
    """Main entry point for the agent worker CLI."""
    parser = argparse.ArgumentParser(
        description="Run an agent worker that consumes tasks from SQS"
    )
    parser.add_argument(
        "--agent-type",
        type=str,
        required=True,
        choices=["coder", "reviewer", "validator"],
        help="Type of agent to run",
    )
    parser.add_argument(
        "--queue-url",
        type=str,
        help="SQS queue URL (overrides environment variable)",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        help="Maximum number of tasks to process before stopping",
    )
    parser.add_argument(
        "--use-mock-llm",
        action="store_true",
        help="Use mock LLM for testing",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create LLM client
    llm_client = None
    if args.use_mock_llm:
        from unittest.mock import AsyncMock

        llm_client = AsyncMock()
        llm_client.generate.return_value = '{"status": "PASS"}'
        logger.info("Using mock LLM client")

    # Create and run worker
    worker = create_agent_worker(
        agent_type=args.agent_type,
        queue_url=args.queue_url,
        llm_client=llm_client,
    )

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler() -> None:
        logger.info("Received shutdown signal")
        worker.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Run the worker
    try:
        stats = await worker.run(max_tasks=args.max_tasks)
        logger.info(f"Worker finished: {stats}")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
