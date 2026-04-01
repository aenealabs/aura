"""CLI wrapper for RuntimeIncidentAgent.

This module provides a command-line interface for running incident investigations
in ECS Fargate tasks. It parses incident events and executes the investigation workflow.

Usage:
    python -m src.agents.runtime_incident_cli --incident-id <id> --incident-file <path>

Environment Variables:
    - ENVIRONMENT: dev/qa/prod
    - AWS_DEFAULT_REGION: AWS region (default: us-east-1)
    - LOG_LEVEL: Logging level (default: INFO)
    - ENABLE_LLM: Enable Bedrock LLM for RCA (default: true)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from src.agents.runtime_incident_agent import RuntimeIncidentAgent
from src.services.bedrock_llm_service import BedrockLLMService, BedrockMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


async def run_investigation(
    incident_id: str, incident_event: dict, environment: str
) -> int:
    """
    Run incident investigation.

    Args:
        incident_id: Unique identifier for the incident
        incident_event: EventBridge event containing incident details
        environment: Environment name (dev/qa/prod)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info(f"Initializing RuntimeIncidentAgent for incident: {incident_id}")

        # Initialize BedrockLLMService if enabled
        llm_client = None
        enable_llm = os.environ.get("ENABLE_LLM", "true").lower() == "true"

        if enable_llm:
            try:
                logger.info("Initializing BedrockLLMService...")
                llm_client = BedrockLLMService(
                    mode=BedrockMode.AWS,
                    environment=environment,
                )
                logger.info("BedrockLLMService initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize BedrockLLMService: {e}")
                logger.warning("Continuing without LLM (RCA will use default)")
        else:
            logger.info("LLM disabled via ENABLE_LLM environment variable")

        # Initialize agent with LLM service
        # Note: context_service and mcp_adapters require Neptune/OpenSearch
        # connectivity which will be added in Phase 4
        agent = RuntimeIncidentAgent(
            llm_client=llm_client,
            context_service=None,  # TODO: Initialize in Phase 4 (requires Neptune/OpenSearch)
            mcp_adapters=None,  # TODO: Initialize in Phase 5 (MCP observability adapters)
        )

        logger.info("Starting investigation workflow...")

        # Run investigation
        investigation = await agent.investigate(incident_event)

        logger.info(
            f"Investigation complete. RCA confidence: {investigation.confidence_score}%"
        )
        logger.info(f"Hypothesis: {investigation.rca_hypothesis}")
        logger.info(f"HITL status: {investigation.hitl_status}")

        # Log investigation ID for tracking
        logger.info(f"Investigation stored in DynamoDB: {investigation.incident_id}")

        return 0

    except Exception as e:
        logger.error(f"Investigation failed: {str(e)}", exc_info=True)
        return 1


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="RuntimeIncidentAgent CLI for ECS Fargate tasks"
    )
    parser.add_argument(
        "--incident-id",
        required=True,
        help="Unique identifier for the incident",
    )
    parser.add_argument(
        "--incident-file",
        required=True,
        type=Path,
        help="Path to JSON file containing incident event",
    )
    parser.add_argument(
        "--environment",
        default="dev",
        choices=["dev", "qa", "prod"],
        help="Environment name (default: dev)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("=" * 60)
    logger.info("RuntimeIncidentAgent CLI (ADR-025)")
    logger.info("=" * 60)
    logger.info(f"Incident ID: {args.incident_id}")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Incident File: {args.incident_file}")
    logger.info("=" * 60)

    # Load incident event from file
    try:
        with open(args.incident_file, "r") as f:
            incident_event = json.load(f)
            logger.info("Incident event loaded successfully")
    except FileNotFoundError:
        logger.error(f"Incident file not found: {args.incident_file}")
        return 2
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in incident file: {e}")
        return 2

    # Set environment variable for services
    os.environ["ENVIRONMENT"] = args.environment
    os.environ["AURA_ENV"] = args.environment

    # Run investigation
    exit_code = asyncio.run(
        run_investigation(args.incident_id, incident_event, args.environment)
    )

    if exit_code == 0:
        logger.info("Investigation completed successfully")
    else:
        logger.error("Investigation failed")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
